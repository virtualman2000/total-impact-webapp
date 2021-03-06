from totalimpactwebapp import db
import util
import configs
import datetime
import jinja2
import numpy
import logging
from collections import defaultdict
from collections import Counter

logger = logging.getLogger("ti.card")


def get_metrics_by_name(products, provider, interaction):
    matching_metrics = []
    for product in products:
        metric = product.get_metric_by_name(provider, interaction)
        if metric:
            matching_metrics.append(metric)
    return matching_metrics

def get_metrics_by_engagement(products, engagement):
    matching_metrics = []
    all_possible_metrics_config_dicts = configs.metrics().values()

    for product in products:
        for config_dict in all_possible_metrics_config_dicts:
            if config_dict["engagement_type"]==engagement:
                provider = config_dict["provider"]
                interaction = config_dict["interaction"]
                metric = product.get_metric_by_name(provider, interaction)
                if metric:
                    matching_metrics.append(metric)
    return matching_metrics

def get_tweeter_followers(products):
    tweeter_followers = Counter()
    for product in products:
        product_follower_metric = product.get_metric_by_name("altmetric_com", "tweeter_followers")
        if product_follower_metric:
            for follower in product_follower_metric.most_recent_snap.raw_value:
                twitter_handle, followers = tuple(follower)
                tweeter_followers[twitter_handle.lower()] = followers
        # except (AttributeError, TypeError):
        #     logger.error("error counting twitter_followers")
    return tweeter_followers


class Card(object):

    def __init__(self, **kwargs):
        if "timestamp" in kwargs and kwargs["timestamp"]:
            self.timestamp = kwargs["timestamp"]
        else:
            self.timestamp = datetime.datetime.utcnow()


    @classmethod
    def would_generate_a_card(self):
        raise NotImplementedError

    def get_template_name(self):
        raise NotImplementedError

    @property
    def card_type(self):
        return type(self).__name__


    @property
    def card_type_short(self):
        if "metric" in self.card_type.lower():
            return "metric"
        if "engagement" in self.card_type.lower():
            return "engagement"
        if "diff" in self.card_type.lower():
            return "diff"
        return self.card_type.lower().replace("card", "")


    @property
    def sort_by(self):
        score = 0

        if self.milestone_awarded == 1:
            score += 500  # as good as a 75th percentile

        if self.milestone_awarded > 1:
            score += (self.milestone_awarded + 500)

        if "youtube"==self.provider:
            score += 1000
        elif "wikipedia"==self.provider:
            score += 10000

        return score


    def to_html(self):
        templateLoader = jinja2.FileSystemLoader(searchpath="totalimpactwebapp/templates")
        templateEnv = jinja2.Environment(loader=templateLoader)
        html_template = templateEnv.get_template(self.get_template_name() + ".html")
        return html_template.render({"card": self})

    def to_text(self):
        templateLoader = jinja2.FileSystemLoader(searchpath="totalimpactwebapp/templates")
        templateEnv = jinja2.Environment(loader=templateLoader)
        html_template = templateEnv.get_template(self.get_template_name() + ".txt")
        return html_template.render(self)

    def to_dict(self):
        # ignore some properties to keep dict small.   
        properties_to_ignore = ["profile", "product"]
        ret = util.dict_from_dir(self, properties_to_ignore)

        # individual cards can add in more subelements to help with debugging
        ret["url_slug"] = self.profile.url_slug

        return ret



class ProductNewDiffCard(Card):

    def __init__(self, products, product, metric, url_slug=None, timestamp=None):
        self.url_slug = url_slug
        self.products = products
        self.product = product
        self.metric = metric
        super(ProductNewDiffCard, self).__init__(timestamp=timestamp)

    @classmethod
    def would_generate_a_card(cls, metric):
        # a milestone can be awarded if the previous value was 0, 
        # which would mean there is no diff_value
        return metric.diff_value > 0

    @property
    def num_profile_products_this_good(self):
        ret = 0
        for product in self.products:
            if product.has_metric_this_good(
                    self.metric.provider,
                    self.metric.interaction,
                    self.metric.display_count):
                ret += 1
        return ret

    @property
    def num_profile_products_this_good_ordinal(self):
        return util.ordinal(self.num_profile_products_this_good)

    @property
    def milestone_awarded(self):
        return self.metric.milestone_just_reached

    @property
    def provider(self):
        return self.metric.provider

    @property
    def sort_by(self):
        score = super(ProductNewDiffCard, self).sort_by

        if self.metric.percentile and self.metric.percentile["value"] > 50:
            top_half = self.metric.percentile["value"] - 50
            score += (top_half * 10)  # max 500

        try:
            if "plos"==self.metric.provider or "slideshare"==self.metric.provider:
                score += int(self.metric.diff_value)
            elif "scopus"==self.metric.provider:
                score += (int(self.metric.diff_value) * 100)
            else:
                score += (int(self.metric.diff_value) * 10)
        except TypeError:
            # no diff value because is first metric card
            pass

        return score


    def get_template_name(self):
        return "card-product"

    def to_dict(self):
        mydict = super(ProductNewDiffCard, self).to_dict()
        mydict.update({
            "tiid": self.product.tiid,
            })
        return mydict







class AbstractProductsAccumulationCard(Card):

    def __init__(self, products, provider, interaction, url_slug=None, timestamp=None):
        self.url_slug = url_slug
        self.products = products
        self.provider = provider
        self.interaction = interaction

        # this card doesn't have a solo metric object, but it helps to 
        # save an exemplar metric so that it can be used to access relevant display properies
        try:
            self.exemplar_metric = get_metrics_by_name(self.products, provider, interaction)[0] #exemplar metric 
        except IndexError:
            pass
        super(AbstractProductsAccumulationCard, self).__init__(timestamp=timestamp)


    @classmethod
    def would_generate_a_card(cls, products, provider, interaction):
        return cls.metric_accumulations(products, provider, interaction) is not None

    @property
    def milestone_awarded(self):
        try:
            return self.metric_accumulations(self.products, self.provider, self.interaction)["milestone"]
        except (KeyError, TypeError):
            return None

    @property
    def num_products(self):
        return len(self.products)

    @property
    def current_value(self):
        try:
            return self.metric_accumulations(self.products, self.provider, self.interaction)["accumulated_diff_end_value"]
        except (KeyError, TypeError):
            return None

    @property
    def diff_value(self):
        try:
            return self.metric_accumulations(self.products, self.provider, self.interaction)["accumulated_diff"]
        except (KeyError, TypeError):
            return None                        

    @property
    def sort_by(self):
        score = super(AbstractProductsAccumulationCard, self).sort_by
        return score + 1000

    def to_dict(self):
        # ignore some properties to keep dict small.   
        properties_to_ignore = [
            "exemplar_metric", 
            "products"
            ]
        ret = util.dict_from_dir(self, properties_to_ignore)
        return ret


class AbstractNewDiffCard(AbstractProductsAccumulationCard):

    def get_template_name(self):
        return "card-profile"

    @classmethod
    def metric_accumulations(cls, products, provider, interaction):
        matching_metrics = get_metrics_by_name(products, provider, interaction)

        metrics_with_diffs = [m for m in matching_metrics if m.can_diff]

         # quit if there's no matching metrics or they dont' have no diffs
        if not len(metrics_with_diffs):
            return None

        accumulated_diff_start_value = sum([m.diff_window_start_value for m in metrics_with_diffs])
        accumulated_diff_end_value = sum([m.diff_window_end_value for m in metrics_with_diffs])
        accumulated_diff = accumulated_diff_end_value - accumulated_diff_start_value

        # milestones will be the same in all the metrics so just grab the first one
        milestones = matching_metrics[0].config["milestones"]

        # see if we just passed any of them
        for milestone in sorted(milestones, reverse=True):
            if accumulated_diff_start_value < milestone <= accumulated_diff_end_value:
                return ({
                    "milestone": milestone, 
                    "accumulated_diff_end_value": accumulated_diff_end_value,
                    "accumulated_diff": accumulated_diff
                    })
        return None


class ProfileNewDiffCard(AbstractNewDiffCard):
    def get_template_name(self):
        return "card-profile"


class GenreNewDiffCard(AbstractNewDiffCard):
    @property
    def genre(self):
        return self.products[0].genre

    def to_dict(self):
        # ignore some properties to keep dict small.   
        properties_to_ignore = [
            "url_slug", 
            "exemplar_metric", 
            "products"
            ]
        ret = util.dict_from_dir(self, properties_to_ignore)
        return ret


class GenreMetricSumCard(AbstractProductsAccumulationCard):
    @classmethod
    def would_generate_a_card(cls, products, provider, interaction):
        if cls.metric_accumulations(products, provider, interaction) is not None:
            try:
                exemplar_metric = get_metrics_by_name(products, provider, interaction)[0] #exemplar metric 
                if exemplar_metric.engagement_type not in ["viewed", "saved"]:
                    return True
            except IndexError:
                pass       
        return False

    @property
    def genre(self):
        return self.products[0].genre

    @property
    def genre_card_address(self):
        return u".".join(["genre", self.genre, "sum", "metric", self.provider, self.interaction])

    @property
    def display_things_we_are_counting(self):
        try:
            plural_interaction = self.exemplar_metric.display_interaction
            if not plural_interaction.endswith("s"):
                plural_interaction += "s"    
        except AttributeError:
            plural_interaction = self.interaction + "s" 
        return plural_interaction


    @property
    def img_filename(self):
        return u"{provider}_{interaction}.ico".format(
            provider=self.provider, interaction=self.interaction)


    @property
    def tooltip(self):       
        try:
            return u"{num} {provider} {interaction}".format(
                num=self.current_value, 
                provider=self.exemplar_metric.display_provider,
                interaction=self.display_things_we_are_counting)
        except KeyError:
            return "" 

    @property
    def sort_by(self):
        score = 1000
        if self.provider in ["citeulike", "delicious", "impactstory", "plossearch"]:
            score -= 10000

        if self.provider in ["mendeley", "altmetric_com"]:
            score += 500

        if self.provider in ["scopus"]:
            score += 5000

        if self.current_value:
            score += self.current_value
        
        return score

    @classmethod
    #override with a version that returns all cards, not just ones that freshly pass milestones
    def metric_accumulations(cls, products, provider, interaction):
        matching_metrics = get_metrics_by_name(products, provider, interaction)
        matching_metrics = [m for m in matching_metrics if m.is_int]

        accumulated_diff_start_value = sum([m.diff_window_start_value for m in matching_metrics 
            if m.diff_window_start_value])
        accumulated_diff_end_value = sum([m.diff_window_end_value for m in matching_metrics 
            if m.diff_window_end_value])
        accumulated_diff = accumulated_diff_end_value - accumulated_diff_start_value

        if not accumulated_diff_end_value:
            return None

        # milestones will be the same in all the metrics so just grab the first one
        milestones = matching_metrics[0].config["milestones"]

        # see if we just passed any of them
        for milestone in sorted(milestones, reverse=True):
            if accumulated_diff_start_value < milestone <= accumulated_diff_end_value:
                milestone = milestone
                break

        return ({
            "milestone": milestone, 
            "accumulated_diff_end_value": accumulated_diff_end_value,
            "accumulated_diff": accumulated_diff
            })

    def to_dict(self):
        # ignore some properties to keep dict small.   
        properties_to_ignore = [
            "url_slug", 
            "exemplar_metric", 
            "products"
            ]
        ret = util.dict_from_dir(self, properties_to_ignore)
        return ret


class GenreEngagementSumCard(Card):
    def __init__(self, products, engagement, url_slug=None, timestamp=None):
        self.url_slug = url_slug
        self.products = products
        self.engagement = engagement

        # this card doesn't have a solo metric object, but it helps to 
        # save an exemplar metric so that it can be used to access relevant display properies
        try:
            self.exemplar_metric = get_metrics_by_engagement(self.products, engagement)[0] #exemplar metric 
        except IndexError:
            pass
        super(GenreEngagementSumCard, self).__init__(timestamp=timestamp)

    @classmethod
    def would_generate_a_card(cls, products, engagement):
        if engagement in ["viewed", "saved"]:
            if cls.engagement_accumulations(products, engagement) is not None:
                return True
        return False

    @property
    def genre(self):
        return self.products[0].genre


    @property
    def num_products(self):
        return len(self.products)

    @property
    def genre_card_address(self):
        return u".".join(["genre", self.genre, "sum", "engagement", self.engagement])

    @property
    def display_things_we_are_counting(self):
        engagement_types = configs.award_configs["engagement_types"]
        return engagement_types[self.engagement][0]

    @property
    def img_filename(self):
        return u"{engagement}.png".format(
            engagement=self.engagement)

    @property
    def sort_by(self):
        score = 1000 + self.current_value
        return score

    @property
    def current_value(self):
        try:
            return self.engagement_accumulations(self.products, self.engagement)["accumulated_diff_end_value"]
        except (KeyError, TypeError):
            return None

    @property
    def diff_value(self):
        try:
            return self.engagement_accumulations(self.products, self.engagement)["accumulated_diff"]
        except (KeyError, TypeError):
            return None 

    @property
    def tooltip(self):
        accumulation_string = self.engagement_accumulations(self.products, self.engagement)["accumulated_string"]
        tooltip = u"{current_value} {display_things_we_are_counting}, including: {accumulation_string}".format(
            current_value=self.current_value, 
            display_things_we_are_counting=self.display_things_we_are_counting,
            accumulation_string=accumulation_string)
        return tooltip
        # except KeyError:
        #     return None 

    @classmethod
    #override with a version that returns all cards, not just ones that freshly pass milestones
    def engagement_accumulations(cls, products, engagement):
        matching_metrics = get_metrics_by_engagement(products, engagement)
        matching_metrics = [m for m in matching_metrics if m.is_int]

        accumulated_diff_start_value = sum([m.diff_window_start_value for m in matching_metrics 
            if m.diff_window_start_value])
        accumulated_diff_end_value = sum([m.diff_window_end_value for m in matching_metrics 
            if m.diff_window_end_value])
        accumulated_diff = accumulated_diff_end_value - accumulated_diff_start_value

        accumulated_dict = defaultdict(int)
        for m in matching_metrics:
            plural_interaction = m.display_interaction
            if not plural_interaction.endswith("s"):
                plural_interaction += "s"    
            display_key = u"{provider} {interaction}".format(
                provider=m.display_provider, interaction=plural_interaction)
            accumulated_dict[display_key] += m.diff_window_end_value

        sorted_accumulated_list = sorted(accumulated_dict.iteritems(), key=lambda (k,v): (v,k), reverse=True)

        accumulated_list = [u"<li>{v} {k}</li>".format(k=k, v=v) for (k, v) in sorted_accumulated_list]
        accumulated_string = u"<ul>{li_list}</ul>".format(
            li_list="".join(accumulated_list))

        if not accumulated_diff_end_value:
            return None

        return ({
            "accumulated_diff_end_value": accumulated_diff_end_value,
            "accumulated_diff": accumulated_diff,
            "accumulated_string": accumulated_string
            })

    def to_dict(self):
        # ignore some properties to keep dict small.   
        properties_to_ignore = [
            "url_slug", 
            "exemplar_metric", 
            "products"
            ]
        ret = util.dict_from_dir(self, properties_to_ignore)
        return ret











