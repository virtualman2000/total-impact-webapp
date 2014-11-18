import logging
import arrow
import datetime
import os
import json
import boto
import requests
from collections import Counter
from collections import defaultdict
import flask

# these imports need to be here for sqlalchemy
from totalimpactwebapp import snap
from totalimpactwebapp import metric
from totalimpactwebapp import award
from totalimpactwebapp import interaction
from totalimpactwebapp import reference_set

# regular ol' imports
from totalimpactwebapp import embed_markup
from totalimpactwebapp import countries
from totalimpactwebapp.metric import make_metrics_list
from totalimpactwebapp.metric import make_mendeley_metric
from totalimpactwebapp.biblio import Biblio
from totalimpactwebapp.aliases import Aliases
from totalimpactwebapp.snap import Snap
from totalimpactwebapp.util import dict_from_dir
from totalimpactwebapp.util import cached_property
from totalimpactwebapp.util import commit
from totalimpactwebapp.configs import get_genre_config

from totalimpactwebapp import db
from totalimpactwebapp import configs
from totalimpactwebapp import json_sqlalchemy



percentile_snap_creations = 0

logger = logging.getLogger("tiwebapp.product")
deprecated_genres = ["twitter", "blog"]

ignore_snaps_older_than = arrow.utcnow().replace(days=-27).datetime

snaps_join_string = "and_(Product.tiid==Snap.tiid, " \
                    "Snap.last_collected_date > '{ignore_snaps_older_than}')".format(
    ignore_snaps_older_than=ignore_snaps_older_than)


def make(raw_dict):
    return Product(raw_dict)


def get_product(tiid):
    return Product.query.get(tiid)

def get_products_from_tiids(tiids, ignore_order=False):
    #  @ignore_order makes it slightly faster by not sorting
    unsorted_products = Product.query.filter(Product.tiid.in_(tiids)).all()
    ret = []

    if ignore_order:
        ret = unsorted_products
    else:
        for my_tiid in tiids:
            my_product = [p for p in unsorted_products if p.tiid == my_tiid][0]
            ret.append(my_product)

    return ret


def upload_file_and_commit(product, file_to_upload, db):
    resp = product.upload_file(file_to_upload)
    commit(db)
    return resp

def add_product_embed_markup(tiid):
    product = get_product(tiid)
    product.embed_markup = product.get_embed_markup() #alters an attribute, so caller should commit
    db.session.add(product)
    commit(db)


class Product(db.Model):

    __tablename__ = 'item'
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'))
    tiid = db.Column(db.Text, primary_key=True)
    created = db.Column(db.DateTime())
    last_modified = db.Column(db.DateTime())
    last_update_run = db.Column(db.DateTime())
    removed = db.Column(db.DateTime())
    last_refresh_started = db.Column(db.DateTime())  #ALTER TABLE item ADD last_refresh_started timestamp
    last_refresh_finished = db.Column(db.DateTime()) #ALTER TABLE item ADD last_refresh_finished timestamp
    last_refresh_status = db.Column(db.Text) #ALTER TABLE item ADD last_refresh_status text
    last_refresh_failure_message = db.Column(json_sqlalchemy.JSONAlchemy(db.Text)) #ALTER TABLE item ADD last_refresh_failure_message text
    has_file = db.Column(db.Boolean, default=False)  # alter table item add has_file bool; alter table item alter has_file SET DEFAULT false;
    embed_markup = db.Column(db.Text)  # alter table item add embed_markup text
    pdf_url = db.Column(db.Text)  # alter table item add pdf_url text
    checked_pdf_url = db.Column(db.Boolean, default=False)  # alter table item add checked_pdf_url boolean

    alias_rows = db.relationship(
        'AliasRow',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("item", lazy="subquery")
    )

    biblio_rows = db.relationship(
        'BiblioRow',
        lazy='subquery',
        cascade="all, delete-orphan",
        backref=db.backref("item", lazy="subquery")
    )

    snaps = db.relationship(
        'Snap',
        lazy='subquery',
        cascade='all, delete-orphan',
        backref=db.backref("item", lazy="subquery"),
        primaryjoin=snaps_join_string
    )

    interactions = db.relationship(
        'Interaction',
        lazy='subquery',
        cascade='all, delete-orphan',
        backref=db.backref("item", lazy="subquery")
    )

    @cached_property
    def biblio(self):
        return Biblio(self.biblio_rows)

    @cached_property
    def aliases(self):
        return Aliases(self.alias_rows)

    @cached_property
    def metrics(self):
        my_metrics = make_metrics_list(self.tiid, self.percentile_snaps, self.created)
        return my_metrics

    @cached_property
    def is_true_product(self):
        try:
            if self.biblio.is_account:
                return False
        except AttributeError:
            pass
        return True

    @cached_property
    def is_refreshing(self):
        REFRESH_TIMEOUT_IN_SECONDS = 120
        if self.last_refresh_started and not self.last_refresh_finished:
            last_refresh_started = arrow.get(self.last_refresh_started, 'utc')
            start_time_theshold = arrow.utcnow().replace(seconds=-REFRESH_TIMEOUT_IN_SECONDS)
            if start_time_theshold < last_refresh_started:
                return True

        return False

    @cached_property
    def finished_successful_refresh(self):
        if self.last_refresh_status and self.last_refresh_status.startswith(u"SUCCESS"):
           return True
        return False

    @cached_property
    def genre(self):
        if self.biblio.calculated_genre is not None:
            genre = self.biblio.calculated_genre
        else:
            genre = self.aliases.get_genre()

        if "article" in genre:
            genre = "article"  #disregard whether journal article or conference article for now
        elif "conference" in genre:
            genre = "conference paper"
        elif "chapter" in genre:
            genre = "book chapter"
        elif "dissertation" == genre:
            genre = "thesis"

        return genre

    @cached_property
    def genre_icon(self):
        try:
            return configs.genre_icons[self.genre]
        except KeyError:
            return configs.genre_icons["unknown"]


    #@cached_property
    #def genre_url_representation(self):
    #    return self.display_genre_plural


    @cached_property
    def host(self):
        host = None
        if self.biblio.calculated_host is not None:
            host = self.biblio.calculated_host
        else:
            host = self.aliases.get_host()

        if self.genre == "article":
            # don't return repositories for articles
            host = "unknown"
        return host


    @cached_property
    def mendeley_discipline(self):
        mendeley_metric = make_mendeley_metric(self.tiid, self.snaps, self.created)
        try:
            return mendeley_metric.mendeley_discipine["name"]
        except (AttributeError, TypeError):
            return None

    @cached_property
    def year(self):
        return self.biblio.display_year

    @cached_property
    def display_genre_plural(self):
        return get_genre_config(self.genre)["plural_name"]


    @cached_property
    def genre_url_key(self):
        return get_genre_config(self.genre)["url_representation"]


    @cached_property
    def fulltext_cta(self):
        return get_genre_config(self.genre)["fulltext_cta"]



    def get_metric_by_name(self, provider, interaction):
        for metric in self.metrics:
            if metric.provider==provider and metric.interaction==interaction:
                return metric
        return None

    @cached_property
    def has_metrics(self):
        return len(self.metrics) > 0

    @cached_property
    def display_title(self):
        return self.biblio.display_title

    @cached_property
    def has_diff(self):
        return any([m.diff_value > 0 for m in self.metrics])

    @cached_property
    def awards(self):
        return award.make_list(self.metrics)

    @cached_property
    def snaps_including_interactions(self):
        counts = Counter()
        countries = Counter()
        for interaction in self.interactions:
            counts[(interaction.tiid, interaction.event)] += 1
            countries[interaction.country] += 1

        interaction_snaps = []
        for (tiid, event) in dict(counts):
            new_snap = Snap(tiid=tiid, 
                            interaction=event, 
                            raw_value=counts[(tiid, event)],
                            provider="impactstory", 
                            last_collected_date=datetime.datetime.utcnow())
            interaction_snaps.append(new_snap)

        new_snap = Snap(tiid=self.tiid, 
                        interaction="countries", 
                        raw_value=dict(countries),
                        provider="impactstory", 
                        last_collected_date=datetime.datetime.utcnow())
        interaction_snaps.append(new_snap)            

        return self.snaps + interaction_snaps

    @cached_property
    def percentile_snaps(self):

        my_refset = reference_set.ProductLevelReferenceSet()
        my_refset.year = self.year
        my_refset.genre = self.genre
        my_refset.host = self.host
        my_refset.title = self.biblio.display_title
        my_refset.mendeley_discipline = self.mendeley_discipline

        ret = []
        for snap in self.snaps_including_interactions:
            snap.set_refset(my_refset)
            ret.append(snap)

        return ret


    @cached_property
    def metrics_raw_sum(self):
        return sum(m.display_count for m in self.metrics)

    @cached_property
    def awardedness_score(self):
        return sum([a.sort_score for a in self.awards])

    @cached_property
    def is_account_product(self):
        try:
            if self.biblio.is_account:
                return True
        except AttributeError:
            pass
        return False

    @cached_property
    def latest_diff_timestamp(self):
        ts_list = [m.latest_nonzero_refresh_timestamp for m in self.metrics]
        if not ts_list:
            return None
        try:
            return sorted(ts_list, reverse=True)[0]
        except IndexError:
            return None

    @cached_property
    def is_free_to_read(self):
        return self.has_file or self.biblio.free_fulltext_host

    @cached_property
    def countries(self):
        my_countries = countries.CountryList()

        altmetric_twitter_metric = self.get_metric_by_name("altmetric_com", "demographics")
        if altmetric_twitter_metric:
            try:
                country_data = altmetric_twitter_metric.most_recent_snap.raw_value["geo"]["twitter"]
                for country in country_data:
                    my_countries.add_from_metric(
                        country,
                        "altmetric_com:tweets",
                        country_data[country]
                    )
            except KeyError:
                pass

        mendeley_views_metric = self.get_metric_by_name("mendeley", "countries")
        if not mendeley_views_metric:
            mendeley_views_metric = self.get_metric_by_name("mendeley_new", "countries")
        if mendeley_views_metric:
            country_data_fullnames = mendeley_views_metric.most_recent_snap.raw_value
            if country_data_fullnames:
                country_data = dict((k, v) for (k, v) in country_data_fullnames.iteritems())
                for country in country_data:
                    my_countries.add_from_metric(
                        country,
                        "mendeley:readers",
                        country_data[country]
                    )

        # impactstory_views_metric = product.get_metric_by_name("impactstory", "my_countries")
        impactstory_views_metric = self.get_metric_by_name("impactstory", "countries")
        if impactstory_views_metric:
            country_data = impactstory_views_metric.most_recent_snap.raw_value
            for country in country_data:
                my_countries.add_from_metric(
                    country,
                    "impactstory:views",
                    country_data[country]
                )
        return my_countries


    def has_metric_this_good(self, provider, interaction, count):
        requested_metric = self.get_metric_by_name(provider, interaction)
        try:
            return requested_metric.display_count >= count
        except AttributeError:
            return False

    def get_file(self):
        if not self.has_file:
            return None

        conn = boto.connect_s3(os.getenv("AWS_ACCESS_KEY_ID"), os.getenv("AWS_SECRET_ACCESS_KEY"))
        bucket_name = os.getenv("AWS_BUCKET", "impactstory-uploads-local")
        bucket = conn.get_bucket(bucket_name, validate=False)

        path = "active"
        key_name = self.tiid + ".pdf"
        full_key_name = os.path.join(path, key_name)
        k = bucket.new_key(full_key_name)

        file_contents = k.get_contents_as_string()
        return file_contents


    # caller should commit because alters an attribute
    def upload_file(self, file_to_upload):

        conn = boto.connect_s3(os.getenv("AWS_ACCESS_KEY_ID"), os.getenv("AWS_SECRET_ACCESS_KEY"))
        bucket_name = os.getenv("AWS_BUCKET", "impactstory-uploads-local")
        bucket = conn.get_bucket(bucket_name, validate=False)

        path = "active"
        key_name = self.tiid + ".pdf"
        full_key_name = os.path.join(path, key_name)
        k = bucket.new_key(full_key_name)

        length = k.set_contents_from_file(file_to_upload)

        self.has_file = True  #alters an attribute, so caller should commit
        self.embed_markup = self.get_embed_markup() #alters an attribute, so caller should commit

        return length

    def get_pdf(self):
        if self.has_file:
            return self.get_file()
        try:
            pdf_url = self.get_pdf_url()
            if pdf_url:
                r = requests.get(pdf_url, timeout=10)
                return r.content
        except (AttributeError, requests.exceptions.Timeout):
            pass
        return None


    def get_pdf_url(self):

        if self.checked_pdf_url:
            return self.pdf_url

        url = None

        if self.aliases.display_pmc:
            url = "http://ukpmc.ac.uk/articles/{pmcid}?pdf=render".format(
                    pmcid=self.aliases.pmc[0])

        elif self.aliases.display_arxiv:
            url = "http://arxiv.org/pdf/{arxiv_id}.pdf".format(
                    arxiv_id=self.aliases.display_arxiv)

        elif hasattr(self.biblio, "free_fulltext_url") and self.biblio.free_fulltext_url:
            # print "trying free fulltext url!"
            # just return right away if pdf is in the link
            if "pdf" in self.biblio.free_fulltext_url:
                url = self.biblio.free_fulltext_url
            
            elif self.aliases.resolved_url and ("sagepub.com/" in self.aliases.resolved_url):
                url = self.aliases.resolved_url + ".full.pdf"

            if not url:
                # since link isn't obviously a pdf, try to get pdf link by scraping page
                url = embed_markup.extract_pdf_link_from_html(self.biblio.free_fulltext_url)

        # got here with nothing else?  use the resolved url if it has pdf in it
        if not url:
            if self.aliases.resolved_url and ("pdf" in self.aliases.resolved_url):
                url = self.aliases.resolved_url

        if url and ".pdf+html" in url:
            url = url.replace(".pdf+html", ".pdf")
        if url and "jstor.org/" in url:
            url = None  # we can't embed jstor urls at the moment

        # do a commit after this
        self.checked_pdf_url = True
        self.pdf_url = url

        return url


    def get_embed_markup(self):
        logger.debug(u"in get_embed_markup for {tiid}".format(
            tiid=self.tiid))

        if self.is_account_product:
            return None

        try:
            if not self.aliases.best_url:
                return None
        except AttributeError:
            return None

        html = None

        if "github" in self.aliases.best_url:
            html = embed_markup.get_github_embed_html(self.aliases.best_url)

        elif "dryad" in self.aliases.best_url:
            html = embed_markup.get_dryad_embed_html(self.aliases.best_url)

        elif "figshare" in self.aliases.best_url:
            html = embed_markup.get_figshare_embed_html(self.aliases.best_url)

        else:
            if self.has_file or self.get_pdf_url():
                try:
                    this_host = flask.request.url_root.strip("/")
                    # workaround for google docs viewer not supporting localhost urls
                    this_host = this_host.replace("localhost:5000", "staging-impactstory.org")
                except RuntimeError:  # when running as a script
                    this_host = "https://impactstory.org"
                url = u"{this_host}/product/{tiid}/pdf".format(
                    this_host=this_host, tiid=self.tiid)

                if url and ("localhost" in url or "127.0.0.1" in url):
                    html = u"<p>Can't view uploaded file on localhost.  View it at <a href='{url}'>{url}</a>.</p>".format(
                            url=url)
                else:
                    if url:
                        try:
                            html = embed_markup.wrap_in_pdf_reader("embed-pdf", url)
                        except UnicodeEncodeError:
                            pass

        if not html and self.genre not in ["article", "unknown"]:
            # this is how we embed slides, videos, etc
            html = embed_markup.wrap_with_embedly(self.aliases.best_url)

        return html


    def __repr__(self):
        return u'<Product {tiid} {best_url}>'.format(
            tiid=self.tiid, best_url=self.aliases.best_url)

    def to_dict(self, keys_to_show="all"):

        print "\n\nproduct.to_dict(). keys: ", dir(self)

        if keys_to_show=="all":
            attributes_to_ignore = [
                "profile",
                "alias_rows",
                "biblio_rows",
                "percentile_snaps",
                "snaps",
                "interactions",
                "snaps_including_interactions"
            ]
            ret = dict_from_dir(self, attributes_to_ignore)
        else:
            ret = dict_from_dir(self, keys_to_show=keys_to_show)

        ret["_tiid"] = self.tiid
        return ret

    def to_markup_dict(self, markup, hide_keys=None, show_keys="all"):
        keys_to_show = [
            "tiid",
            "aliases",
            "biblio",
            "awards",
            "genre",
            "genre_icon",
            #"countries",

             # for sorting
            "year",
            "awardedness_score",

            # to show the "view on impactstory" badges
            "embed_markup",
            "fulltext_cta"
        ]
        my_dict = self.to_dict(keys_to_show)

        my_dict["markup"] = markup.make(my_dict)

        if hide_keys is not None:
            for key_to_hide in hide_keys:
                try:
                    del my_dict[key_to_hide]
                except KeyError:
                    pass
        elif show_keys != "all":
            my_small_dict = {}
            for k, v in my_dict.iteritems():
                if k in show_keys:
                    my_small_dict[k] = v

            my_dict = my_small_dict

        return my_dict


    def to_markup_dict_multi(self, markups_dict, hide_keys=None):
        ret = self.to_dict()

        rendered_markups = {}
        for name, markup in markups_dict.iteritems():
            rendered_markups[name] = markup.make(ret)

        ret["markups_dict"] = rendered_markups

        try:
            for key_to_hide in hide_keys:
                try:
                    del ret[key_to_hide]
                except KeyError:
                    pass
        except TypeError:  # hide_keys=None is not iterable
            pass

        return ret






def patch_biblio(tiid, patch_dict):
    pass
    query = u"{core_api_root}/v1/product/{tiid}/biblio?api_admin_key={api_admin_key}".format(
        core_api_root=os.getenv("API_ROOT"),
        tiid=tiid,
        api_admin_key=os.getenv("API_ADMIN_KEY")
    )
    r = requests.patch(
        query,
        data=json.dumps(patch_dict),
        headers={'Content-type': 'application/json', 'Accept': 'application/json'}
    )

    if "free_fulltext_url" in patch_dict.keys():
        product = get_product(tiid)
        product.checked_pdf_url = False
        db.session.add(product)
        commit(db)        
        add_product_embed_markup(tiid)

    return r


































