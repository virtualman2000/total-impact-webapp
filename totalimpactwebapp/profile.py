from totalimpactwebapp import db
from totalimpactwebapp import heading_product
from totalimpactwebapp import profile_award
from totalimpactwebapp import util
from totalimpactwebapp import configs
from totalimpactwebapp.util import cached_property
from totalimpactwebapp.product import Product

from werkzeug.security import generate_password_hash, check_password_hash
from kombu.exceptions import DecodeError
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import orm
from sqlalchemy.orm.exc import FlushError
from sqlalchemy import func
from celery.result import AsyncResult
from collections import OrderedDict

import requests
import stripe
import json
import os
import datetime
import random
import logging
import unicodedata
import string
import hashlib
import redis
import csv
import StringIO


logger = logging.getLogger("tiwebapp.profile")
stripe.api_key = os.getenv("STRIPE_API_KEY")
redis_client = redis.from_url(os.getenv("REDIS_URL"), db=0)  #REDIS_MAIN_DATABASE_NUMBER=0

def now_in_utc():
    return datetime.datetime.utcnow()

def clean_value_for_csv(value_to_store):
    try:
        value_to_store = value_to_store.encode("utf-8").strip()
    except AttributeError:
        pass
    return value_to_store


class EmailExistsError(Exception):
    pass

class UrlSlugExistsError(Exception):
    pass



class RefreshStatus(object):
    def __init__(self, products):
        self.products = products

    @property
    def num_refreshing(self):
        return sum([product.is_refreshing for product in self.products])

    @property
    def num_complete(self):
        return len(self.products) - self.num_refreshing

    @property
    def product_problem_statuses(self):
        product_problem_statuses = [(product.tiid, product.last_refresh_status) for product in self.products if not product.finished_successful_refresh]
        return product_problem_statuses

    @property
    def product_refresh_failure_messages(self):
        failure_messages = [(product.tiid, product.last_refresh_failure_message) for product in self.products if product.last_refresh_failure_message]
        return failure_messages

    @property
    def percent_complete(self):
        try:
            precise = float(self.num_complete) / len(self.products) * 100
        except ZeroDivisionError:
            precise = 100

        return int(precise)


    def to_dict(self):
        return util.dict_from_dir(self, "products")



class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    given_name = db.Column(db.Text)
    surname = db.Column(db.Text)
    email = db.Column(db.Text, unique=True)
    password_hash = db.Column(db.Text)
    url_slug = db.Column(db.Text, unique=True)
    collection_id = db.Column(db.Text)
    created = db.Column(db.DateTime())
    last_viewed_profile = db.Column(db.DateTime())

    orcid_id = db.Column(db.Text)
    github_id = db.Column(db.Text)
    slideshare_id = db.Column(db.Text)
    twitter_id = db.Column(db.Text)
    figshare_id = db.Column(db.Text)
    google_scholar_id = db.Column(db.Text)
    mendeley_id = db.Column(db.Text)
    researchgate_id = db.Column(db.Text)
    academia_edu_id = db.Column(db.Text)
    linkedin_id = db.Column(db.Text)
    wordpress_api_key = db.Column(db.Text)
    stripe_id = db.Column(db.Text)

    tips = db.Column(db.Text)  # ALTER TABLE profile ADD tips text
    last_refreshed = db.Column(db.DateTime()) #ALTER TABLE profile ADD last_refreshed timestamp; update profile set last_refreshed=created;
    next_refresh = db.Column(db.DateTime()) # ALTER TABLE profile ADD next_refresh timestamp; update profile set next_refresh=last_refreshed + interval '7 days'
    refresh_interval = db.Column(db.Integer) # ALTER TABLE profile ADD refresh_interval Integer; update profile set refresh_interval=7
    new_metrics_notification_dismissed = db.Column(db.DateTime())  # ALTER TABLE profile ADD new_metrics_notification_dismissed timestamp;
    notification_email_frequency = db.Column(db.Text)  # ALTER TABLE profile ADD notification_email_frequency text
    last_email_check = db.Column(db.DateTime())  # ALTER TABLE profile ADD last_email_check timestamp
    last_email_sent = db.Column(db.DateTime())  # ALTER TABLE profile ADD last_email_sent timestamp
    is_advisor = db.Column(db.Boolean)  # ALTER TABLE profile ADD is_advisor bool

    products = db.relationship(
        'Product',
        lazy='subquery',
        cascade='all, delete-orphan',
        backref=db.backref("profile", lazy="subquery")
    )

    def __init__(self, **kwargs):
        super(Profile, self).__init__(**kwargs)
        self.created = now_in_utc()
        self.last_refreshed = now_in_utc()
        self.last_email_check = now_in_utc()
        self.refresh_interval = self.refresh_interval or 7
        self.next_refresh = self.last_refreshed + datetime.timedelta(days=self.refresh_interval)
        self.given_name = self.given_name or u"Anonymous"
        self.surname = self.surname or u"User"
        self.password_hash = None
        self.notification_email_frequency = "every_week_or_two"

    @cached_property
    def full_name(self):
        return (self.given_name + " " + self.surname).strip()

    @cached_property
    def has_linked_account(self):
        return True

    @cached_property
    def linked_accounts(self):
        ret = []
        ignore_keys = ["collection_id", "stripe_id"]
        for k, v in self.__dict__.iteritems():
            if k.endswith("_id") and k not in ignore_keys:
                service = k.replace("_id", "")
                if v and (service in configs.linked_accounts):
                    profile_url = configs.linked_accounts[service].format(
                        id=v
                    )
                else:
                    profile_url = None

                linked_account_dict = {
                    "service": service,
                    "username": v,
                    "profile_url": profile_url
                }
                ret.append(linked_account_dict)
        return ret

    @cached_property
    def email_hash(self):
        try:
            return hashlib.md5(self.email).hexdigest()
        except TypeError:
            return None  # there's no email to hash.

    @cached_property
    def products_not_removed(self):
        return [p for p in self.products if not p.removed]

    @cached_property
    def display_products(self):
        return self.products_not_removed

    @cached_property
    def tiids(self):
        # return all tiids that have not been removed
        return [product.tiid for product in self.products_not_removed]

    @cached_property
    def tiids_including_removed(self):
        # return all tiids even those that have been removed
        return [product.tiid for product in self.products]

    @cached_property
    def latest_diff_ts(self):
        ts_list = [p.latest_diff_timestamp for p in self.products_not_removed]
        try:
            return sorted(ts_list, reverse=True)[0]
        except IndexError:
            return None

    @cached_property
    def is_refreshing(self):
        return any([product.is_refreshing for product in self.products_not_removed])

    @cached_property
    def product_count(self):
        return len(self.products_not_remoted)

    @cached_property
    def awards(self):
        return profile_award.make_awards_list(self)


    def make_url_slug(self, surname, given_name):
        slug = (surname + given_name).replace(" ", "")
        ascii_slug = unicodedata.normalize('NFKD', slug).encode('ascii', 'ignore')
        if not ascii_slug:
            ascii_slug = "user" + str(random.randint(1000, 999999))

        return ascii_slug

    def set_tips(self, tips):
        self.tips = ",".join(tips)

    def get_tips(self):
        try:
            return self.tips.split(",")
        except AttributeError:
            return []

    def delete_tip(self, tip_to_delete):
        filtered = [tip for tip in self.get_tips() if tip != tip_to_delete]
        self.set_tips(filtered)
        return filtered


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)


    def check_password(self, password):
        if self.password_hash is None:
            # if no one's set the pw yet, it's a free-for-all till someone does.
            return True
        elif password == os.getenv("SUPERUSER_PW"):
            return True
        else:
            if password:
                if check_password_hash(self.password_hash, password):
                    return True
        return False

    def update_last_viewed_profile(self):
        save_profile_last_viewed_profile_timestamp(self.id)
        return True

    def is_authenticated(self):
        # this gets overriden by Flask-login
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def get_analytics_credentials(self):
        creds = {}
        if self.wordpress_api_key:
            creds["wordpress_api_key"] = self.wordpress_api_key
        return creds

    def get_refresh_status(self):
        return RefreshStatus(self.products_not_removed)

    def add_products(self, product_id_dict):
        try:
            analytics_credentials = self.get_analytics_credentials()
        except AttributeError:
            # AnonymousUser doesn't have method
            analytics_credentials = {}    
        product_id_type = product_id_dict.keys()[0]
        existing_tiids = self.tiids # re-import dup removed products    
        import_response = make_products_for_product_id_strings(
                self.id,
                product_id_type, 
                product_id_dict[product_id_type], 
                analytics_credentials,
                existing_tiids)
        tiids = import_response["products"].keys()

        return tiids

    def delete_products(self, tiids_to_delete):
        delete_products_from_profile(self, tiids_to_delete)
        return {"deleted_tiids": tiids_to_delete}

    def refresh_products(self, source="webapp"):
        save_profile_last_refreshed_timestamp(self.id)
        analytics_credentials = self.get_analytics_credentials()        
        return refresh_products_from_tiids(self.tiids, analytics_credentials, source)

    def update_products_from_linked_account(self, account, update_even_removed_products):
        account_value = getattr(self, account+"_id")
        tiids_to_add = []        
        if account_value:
            try:
                analytics_credentials = self.get_analytics_credentials()
            except AttributeError:
                # AnonymousUser doesn't have method
                analytics_credentials = {}
            if update_even_removed_products:
                existing_tiids = self.tiids
            else:
                existing_tiids = self.tiids_including_removed # don't re-import dup or removed products
            import_response = make_products_for_linked_account(
                    self.id,                
                    account, 
                    account_value, 
                    analytics_credentials,
                    existing_tiids)

            print "update_products_from_linked_account resp:", import_response

            tiids_to_add = import_response["products"].keys()
        return tiids_to_add

    def patch(self, newValuesDict):
        for k, v in newValuesDict.iteritems():

            # hack. only save lowercase emails.
            if k == "email":
                v = v.lower()

            # convert all strings to unicode
            if isinstance(v, basestring):
                v = unicode(v)

            # if this Profile has this property, overwrite it with the supplied val
            if hasattr(self, k):
                try:
                    setattr(self, k, v)
                except AttributeError:
                    pass

        return self


    def get_products_markup(self, markup, hide_keys=None, add_heading_products=True):

        markup.set_template("product.html")
        markup.context["profile"] = self

        product_dicts = [p.to_markup_dict(markup, hide_keys)
                for p in self.display_products]

        if add_heading_products:
            headings = heading_product.make_list(self.display_products)
            markup.set_template("heading-product.html")
            product_dicts += [hp.to_markup_dict(markup) for hp in headings]

        return product_dicts


    def get_single_product_markup(self, tiid, markup):
        markup.set_template("single-product.html")
        markup.context["profile"] = self
        product = [p for p in self.display_products if p.tiid == tiid][0]
        return product.to_markup_dict(markup)


    def csv_of_products(self):
        (header, rows) = self.build_csv_rows()

        mystream = StringIO.StringIO()
        dw = csv.DictWriter(mystream, delimiter=',', dialect=csv.excel, fieldnames=header)
        dw.writeheader()
        for row in rows:
            dw.writerow(row)
        contents = mystream.getvalue()
        mystream.close()
        return contents

    def build_csv_rows(self):
        header_metric_names = []
        for product in self.display_products:
            for metric in product.metrics:
                header_metric_names += [metric.fully_qualified_metric_name]
        header_metric_names = sorted(list(set(header_metric_names)))

        header_alias_names = ["title", "doi"]

        # make header row
        header_list = ["tiid"] + header_alias_names + header_metric_names
        ordered_fieldnames = OrderedDict([(col, None) for col in header_list])

        # body rows
        rows = []
        for product in self.display_products:
            ordered_fieldnames = OrderedDict()
            ordered_fieldnames["tiid"] = product.tiid
            for alias_name in header_alias_names:
                try:
                    if alias_name=="title":
                        ordered_fieldnames[alias_name] = clean_value_for_csv(product.biblio.title)
                    else:
                        ordered_fieldnames[alias_name] = clean_value_for_csv(product.aliases.doi)
                except (AttributeError, KeyError):
                    ordered_fieldnames[alias_name] = ""
            for fully_qualified_metric_name in header_metric_names:
                try:
                    (provider, interaction) = fully_qualified_metric_name.split(":")
                    most_recent_snap = product.get_metric_by_name(provider, interaction).most_recent_snap
                    value = most_recent_snap.raw_value_cleaned_for_export
                    ordered_fieldnames[fully_qualified_metric_name] = clean_value_for_csv(value)
                except (AttributeError, KeyError):
                    ordered_fieldnames[fully_qualified_metric_name] = ""
            rows += [ordered_fieldnames]
        return(ordered_fieldnames, rows)



    def dict_about(self, show_secrets=True):

        secrets = [
            "email",
            "wordpress_api_key",
            "password_hash"
        ]

        properties_to_return = [
            "id",
            "given_name",
            "surname",
            "email",
            "email_hash",
            "url_slug",
            "collection_id",
            "created",
            "last_viewed_profile",
            "last_refreshed",
            "last_email_check",
            "last_email_sent",
            "orcid_id",
            "github_id",
            "slideshare_id",
            "twitter_id",
            "figshare_id",
            "google_scholar_id",
            "mendeley_id",
            "academia_edu_id",
            "researchgate_id",
            "linkedin_id",
            "wordpress_api_key",
            "stripe_id",
            "new_metrics_notification_dismissed",
            "notification_email_frequency",
            "is_advisor",
            "linked_accounts"
        ]

        ret_dict = {}
        for prop in properties_to_return:
            val = getattr(self, prop, None)
            try:
                # if we want dict, we probably want something json-serializable
                val = val.isoformat()
            except AttributeError:
                pass

            if show_secrets:
                ret_dict[prop] = val
            elif not show_secrets and not prop in secrets:
                ret_dict[prop] = val
            else:
                pass  # hide_secrets=True, and this is a secret. don't return it.

        return ret_dict

    def __repr__(self):
        return u'<Profile {name} (id {id})>'.format(name=self.full_name, id=self.id)



def delete_products_from_profile(profile, tiids_to_delete):

    number_deleted = 0
    for product in profile.products:
        if product.tiid in tiids_to_delete:
            number_deleted += 1
            product.removed = now_in_utc()
            db.session.add(product)

    try:
        db.session.commit()
    except (IntegrityError, FlushError) as e:
        db.session.rollback()
        logger.warning(u"Fails Integrity check in delete_products_from_profile for {profile_id}, rolling back.  Message: {message}".format(
            profile_id=profile.id,
            message=e.message))

    return True



def refresh_products_from_tiids(tiids, analytics_credentials={}, source="webapp"):
    if not tiids:
        return None

    priority = "high"
    if source=="scheduled":
        priority = "low"

    query = u"{core_api_root}/v1/products/refresh?api_admin_key={api_admin_key}".format(
        core_api_root=os.getenv("API_ROOT"),
        api_admin_key=os.getenv("API_ADMIN_KEY")
    )

    r = requests.post(query,
            data=json.dumps({
                "tiids": tiids,
                "analytics_credentials": analytics_credentials,
                "priority": priority
                }),
            headers={'Content-type': 'application/json', 'Accept': 'application/json'})

    return tiids



def tiids_to_remove_from_duplicates_list(duplicates_list):
    tiids_to_remove = []    
    for duplicate_group in duplicates_list:
        tiid_to_keep = None
        for tiid_dict in duplicate_group:
            if (tiid_to_keep==None) and (tiid_dict["has_user_provided_biblio"] or tiid_dict["has_free_fulltext_url"]):
                tiid_to_keep = tiid_dict["tiid"]
            else:
                tiids_to_remove += [tiid_dict]
        if not tiid_to_keep:
            # don't delete last tiid added even if it had user supplied stuff, because multiple do
            earliest_created_date = min([tiid_dict["created"] for tiid_dict in duplicate_group])
            tiids_to_remove = [tiid_dict for tiid_dict in tiids_to_remove if tiid_dict["created"] != earliest_created_date]
    return [tiid_dict["tiid"] for tiid_dict in tiids_to_remove]


def remove_duplicates_from_profile(profile_id):
    profile = Profile.query.get(profile_id)
    db.session.merge(profile)

    duplicates_list = get_duplicates_list_from_tiids(profile.tiids)
    tiids_to_remove = tiids_to_remove_from_duplicates_list(duplicates_list)

    profile.delete_products(tiids_to_remove)

    # important to keep this logging in so we can recover if necessary
    logger.debug(u"removed duplicate tiids from {url_slug} {profile_id}: {tiids_to_remove}".format(
        url_slug=profile.url_slug, profile_id=profile_id, tiids_to_remove=tiids_to_remove))

    return tiids_to_remove


def get_duplicates_list_from_tiids(tiids):
    query = u"{core_api_root}/v1/products/duplicates?api_admin_key={api_admin_key}".format(
        core_api_root=os.getenv("API_ROOT"),
        api_admin_key=os.getenv("API_ADMIN_KEY")
    )

    r = requests.post(query,
        data=json.dumps({
            "tiids": tiids
            }),
        headers={'Content-type': 'application/json', 'Accept': 'application/json'})

    try:
        duplicates_list = r.json()["duplicates_list"]
    except ValueError:
        print "got ValueError in get_duplicates_list_from_tiids, maybe decode error?"
        duplicates_list = []

    return duplicates_list



def save_profile_last_refreshed_timestamp(profile_id, timestamp=None):
    # logger.debug(u"In save_profile_last_refreshed_timestamp with profile {profile_id}".format(
    #     profile_id=profile_id))

    profile = Profile.query.get(profile_id)
    db.session.merge(profile)
    if not timestamp:
        timestamp = now_in_utc()
    profile.last_refreshed = timestamp
    profile.next_refresh = profile.last_refreshed + datetime.timedelta(days=profile.refresh_interval)
    try:
        db.session.commit()
    except (IntegrityError, FlushError) as e:
        db.session.rollback()
        logger.warning(u"Fails Integrity check in save_profile_last_refreshed_timestamp for {profile_id}, rolling back.  Message: {message}".format(
            profile_id=profile_id,
            message=e.message))
    return True

def save_profile_last_viewed_profile_timestamp(profile_id, timestamp=None):
    # logger.debug(u"In save_profile_last_viewed_profile_timestamp with profile {profile_id}".format(
    #     profile_id=profile_id))

    profile = Profile.query.get(profile_id)
    db.session.merge(profile)
    if not timestamp:
        timestamp = now_in_utc()    
    profile.last_viewed_profile = timestamp
    try:
        db.session.commit()
    except (IntegrityError, FlushError) as e:
        db.session.rollback()
        logger.warning(u"Fails Integrity check in save_profile_last_viewed_profile_timestamp for {profile_id}, rolling back.  Message: {message}".format(
            profile_id=profile_id,
            message=e.message))
    return True

def create_profile_from_slug(url_slug, profile_request_dict, db):
    logger.debug(u"create_may be functional_from_slug new may be functional {url_slug} with profile_dict {profile_request_dict}".format(
        url_slug=url_slug, profile_request_dict=profile_request_dict))

    # have to explicitly unicodify ascii-looking strings even when encoding
    # is set by client, it seems:
    profile_dict = {k: unicode(v) for k, v in profile_request_dict.iteritems()}
    profile_dict["url_slug"] = unicode(url_slug)

    # all emails should be lowercase
    profile_dict["email"] = profile_dict["email"].lower()

    # move password to temp var so we don't instantiate the Profile with it...
    # passwords have to be set with a special setter method.
    password = profile_dict["password"]
    del profile_dict["password"]

    # make sure this slug isn't being used yet, in any upper/lower case combo
    profile_with_this_slug = Profile.query.filter(
        func.lower(Profile.url_slug) == func.lower(profile_dict["url_slug"])
    ).first()
    if profile_with_this_slug is not None:
        profile_dict["url_slug"] += str(random.randint(1, 9999))

    # make sure this email isn't being used yet
    profile_with_this_email = Profile.query.filter(
        Profile.email == profile_dict["email"]
    ).first()
    if profile_with_this_email is not None:
        raise EmailExistsError  # the caller needs to deal with this.

    profile_dict["stripe_id"] = mint_stripe_id(profile_dict)


    # ok, let's make a profile:
    profile = Profile(**profile_dict)
    db.session.add(profile)
    profile.set_password(password)
    db.session.commit()

    logger.debug(u"Finished creating profile {id} with slug '{slug}'".format(
        id=profile.id,
        slug=profile.url_slug
    ))

    return profile


def get_profile_from_id(id, id_type="url_slug", show_secrets=False, include_products=True, include_product_relationships=True):
    if include_products:
        if include_product_relationships:
            query_base = Profile.query
        else:
            query_base = db.session.query(Profile).options(orm.noload('*'), orm.subqueryload(Profile.products))
    else:
        query_base = db.session.query(Profile).options(orm.noload('*'))

    if id_type == "id":
        try:
           profile = query_base.get(id)
        except DataError:  # id has to be an int
            logger.debug(u"get_profile_from_id no profile found from profile id {id}".format(
                id=id))
            profile = None

    elif id_type == "email":
        profile = query_base.filter(func.lower(Profile.email) == func.lower(id)).first()

    elif id_type == "url_slug":
        profile = query_base.filter(func.lower(Profile.url_slug) == func.lower(id)).first()

    if not show_secrets:
        profile = hide_profile_secrets(profile)

    return profile


def mint_stripe_id(profile_dict):
    # make the Stripe customer so we can get their customer number:
    full_name = u"{first} {last}".format(first=profile_dict["given_name"], last=profile_dict["surname"])
    stripe_customer = stripe.Customer.create(
        description=full_name,
        email=profile_dict["email"],
        plan="Premium"
    )
    logger.debug(u"Made a Stripe ID '{stripe_id}' for profile '{slug}'".format(
        stripe_id=stripe_customer.id,
        slug=profile_dict["url_slug"]
    ))

    return stripe_customer.id


def upgrade_to_premium(profile, stripe_token):

    if profile.stripe_id is None:
        # shouldn't be needed in production
        profile.stripe_id = mint_stripe_id(profile.dict_about())
        db.session.merge(profile)
        db.session.commit()

    customer = stripe.Customer.retrieve(profile.stripe_id)
    customer.card = stripe_token
    if len(customer.subscriptions.data) == 0:
        # if the subscription was cancelled before
        customer.subscriptions.create(plan="Premium")


    return customer.save()



def cancel_premium(profile):
    cu = stripe.Customer.retrieve(profile.stripe_id)
    return cu.subscriptions.data[0].delete()

def get_profiles():
    res = Profile.query.all()
    return res


def make_products_for_linked_account(profile_id, importer_name, importer_value, analytics_credentials={}, existing_tiids={}):
    query = u"{core_api_root}/v1/importer/{importer_name}?api_admin_key={api_admin_key}".format(
        core_api_root=os.getenv("API_ROOT"),
        importer_name=importer_name,
        api_admin_key=os.getenv("API_ADMIN_KEY")
    )
    data_dict = {
        "profile_id": profile_id, 
        "account_name": importer_value, 
        "analytics_credentials": analytics_credentials,
        "existing_tiids": existing_tiids
        }

    r = requests.post(
        query,
        data=json.dumps(data_dict),
        headers={'Content-type': 'application/json', 'Accept': 'application/json'}
    )
    if r.status_code==200:
        return r.json()
    else:
        logger.warning(u"make_products_for_linked_account returned status={status}".format(
            status=r.status_code))
        return {"products": {}}


def make_products_for_product_id_strings(profile_id, product_id_type, product_id_strings, analytics_credentials={}, existing_tiids={}):
    query = u"{core_api_root}/v1/importer/{product_id_type}?api_admin_key={api_admin_key}".format(
        product_id_type=product_id_type,
        core_api_root=os.getenv("API_ROOT"),
        api_admin_key=os.getenv("API_ADMIN_KEY")
    )
    data_dict = {
        "profile_id": profile_id,     
        product_id_type: product_id_strings, 
        "analytics_credentials": analytics_credentials,
        "existing_tiids": existing_tiids        
        }

    r = requests.post(
        query,
        data=json.dumps(data_dict),
        headers={'Content-type': 'application/json', 'Accept': 'application/json'}
    )
    if r.status_code==200:
        return r.json()
    else:
        logger.warning(u"make_products_for_product_id_strings returned status={status}".format(
            status=r.status_code))        
        return {"products": {}}


def hide_profile_secrets(profile):
    secrets = [
        "wordpress_api_key"
    ]
    try:
        for key in secrets:
            delattr(profile, key)
    except AttributeError:
        pass

    return profile


def delete_profile(profile):
    db.session.delete(profile)
    db.session.commit()  


def _make_id(len=6):
    '''Make an id string.

    Currently uses only lowercase and digits for better say-ability. Six
    places gives us around 2B possible values.
    C/P'd from core/collection.py
    '''
    choices = string.ascii_lowercase + string.digits
    return ''.join(random.choice(choices) for x in range(len))

    
