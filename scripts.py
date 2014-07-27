import stripe
import random
import logging
from totalimpactwebapp.profile import Profile
from totalimpactwebapp import db

logger = logging.getLogger("tiwebapp.scripts")

"""
requires these env vars be set in this environment:
DATABASE_URL
STRIPE_API_KEY
"""


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


def mint_stripe_customers_for_all_profiles():

    for profile in page_query(Profile.query):

        if profile.stripe_id:
            print "Already a Stripe customer for {email}; skipping".format(
                email=profile.email
            )
            continue


        print "making a Stripe customer for {email} ".format(email=profile.email)
        full_name = "{first} {last}".format(
            first=profile.given_name,
            last=profile.surname
        )
        stripe_customer = stripe.Customer.create(
            description=full_name,
            email=profile.email,
            plan="base"
        )

        print "Successfully made stripe id " + stripe_customer.id

        profile.stripe_id = stripe_customer.id
        db.session.merge(profile)

    print "Done minting Stripe customer; committing profiles to db."
    db.session.commit()
    print "Comitted to db. All donesies!"


def write_500_random_profile_urls():
    urls = []
    sample_size = 500
    for profile in page_query(Profile.query):
        products_count = len(profile.tiids)
        if products_count > 0:
            url = "https://staging-impactstory.org/" + profile.url_slug
            urls.append([products_count, url])
            logger.info(u"getting a new profile url out: {url}".format(
                url=url
            ))

    sampled_urls = random.sample(urls, sample_size)

    logger.info(u"writing our {sample_size} sampled profile URLs".format(
        sample_size=sample_size
    ))

    for row in sampled_urls:
        try:
            print "{products_count},{url}".format(
                products_count=row[0],
                url=row[1]
            )
        except UnicodeEncodeError:
            pass  # whatever, we don't need exactly 500



write_500_random_profile_urls()