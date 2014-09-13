import logging
from totalimpactwebapp.util import cached_property
from totalimpactwebapp.util import dict_from_dir

logger = logging.getLogger("ti.account")


def account_factory(product):
    account = None
    if product.is_account_product:
        if product.host == "twitter":
            account = TwitterAccount(product)
        elif product.host == "github":
            account = GitHubAccount(product)
        elif product.host == "slideshare":
            account = SlideShareAccount(product)

    return account



class Account(object):
    def __init__(self, product):
        self.product = product

    @cached_property
    def display_name(self):
        return self.__class__.__name__.replace("Account", "")

    @cached_property
    def followers(self):
        provider_name = self.display_name.lower()
        follower_metric = self.product.get_metric_by_name(provider_name, "followers")
        if follower_metric:
            return follower_metric.current_value
        else:
            return 0


    def to_dict(self):
        attributes_to_ignore = [
            "product"
        ]
        ret = dict_from_dir(self, attributes_to_ignore)
        return ret



class TwitterAccount(Account):
    pass

class GitHubAccount(Account):
    pass

class SlideShareAccount(Account):
    pass
