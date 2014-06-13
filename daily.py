from totalimpactwebapp.user import User
from totalimpactwebapp.user import ProductsFromCore
from totalimpactwebapp import db
import tasks

from sqlalchemy import func
from celery import chain
import time
import datetime
import argparse
import logging

logger = logging.getLogger("webapp.daily")



"""
requires these env vars be set in this environment:
DATABASE_URL
"""

try:
    # set jason's env variables for local running.
    import config
    config.set_env_vars_from_dot_env()
except ImportError:
    pass


def page_query(q):
    offset = 0
    while True:
        r = False
        for elem in q.limit(5).offset(offset):
           r = True
           yield elem
        offset += 5
        if not r:
            break

def add_profile_deets_for_everyone():
    for user in page_query(User.query.order_by(User.url_slug.asc())):
        logger.info(u"add_profile_deets_for_everyone: {url_slug}".format(url_slug=user.url_slug))
        response = tasks.add_profile_deets.delay(user)


def deduplicate_everyone():
    for user in page_query(User.query.order_by(User.url_slug.asc())):
        logger.info(u"deduplicate_everyone: {url_slug}".format(url_slug=user.url_slug))
        response = tasks.deduplicate.delay(user)



def create_cards_for_everyone(url_slug=None):
    cards = []
    if url_slug:
        user = User.query.filter(func.lower(User.url_slug) == func.lower(url_slug)).first()
        # print user.url_slug        
        cards = tasks.create_cards(user)
    else:    
        for user in page_query(User.query.order_by(User.url_slug.asc())):
            # print user.url_slug        
            cards = tasks.create_cards.delay(user)
    return cards



def email_report_to_url_slug(url_slug=None):
    if url_slug:
        user = User.query.filter(func.lower(User.url_slug) == func.lower(url_slug)).first()
        # print user.url_slug        
        tasks.send_email_report(user)


def email_report_to_everyone_who_needs_one():
    for user in page_query(User.query.order_by(User.url_slug.asc())):

        logger.info(u"clearing user cache for {url_slug}".format(
            url_slug=user.url_slug))

        print len(user.product_objects)

        ProductsFromCore.clear_cache()

        try:
            if not user.email or (u"@" not in user.email):
                logger.info(u"not sending, no email address for {url_slug}".format(url_slug=user.url_slug))
            elif user.notification_email_frequency == "none":
                logger.info(u"not sending, {url_slug} is unsubscribed".format(url_slug=user.url_slug))
            elif user.last_email_sent and ((datetime.datetime.utcnow() - user.last_email_sent).days < 7):
                logger.info(u"not sending, {url_slug} already got email this week".format(url_slug=user.url_slug))
            else:
                logger.info(u"adding ASYNC notification check to celery for {url_slug}".format(url_slug=user.url_slug))
                status = tasks.send_email_if_new_diffs.delay(user.id)
        except Exception as e:
            logger.warning(u"EXCEPTION in email_report_to_everyone_who_needs_one for {url_slug}, skipping to next user.  Error {e}".format(
                url_slug=user.url_slug, e=e))
            pass
    return


def main(function, url_slug):
    if function=="email_report":
        if url_slug:
            email_report_to_url_slug(url_slug)
        else:    
            email_report_to_everyone_who_needs_one()
    elif function=="dedup":
        deduplicate_everyone()
    elif function=="profile_deets":
        add_profile_deets_for_everyone()



if __name__ == "__main__":

    db.create_all()
    
    # get args from the command line:
    parser = argparse.ArgumentParser(description="Run stuff")
    parser.add_argument('--url_slug', default=None, type=str, help="url slug")
    # parser.add_argument('--celery', default=True, type=bool, help="celery")
    parser.add_argument('--function', default="email_report", type=str, help="function")
    args = vars(parser.parse_args())
    print args
    print u"daily.py starting."
    main(args["function"], args["url_slug"])

    db.session.remove()
    


