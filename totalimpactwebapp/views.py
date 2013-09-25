import requests, os, json, logging, re, random, datetime, hashlib
import mandrill
import analytics

from flask import request, send_file, abort, make_response, g, redirect, url_for
from flask import render_template, flash
from flask.ext.assets import Environment, Bundle
from flask.ext.login import login_user, logout_user, current_user, login_required

from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy import func
from itsdangerous import TimestampSigner, SignatureExpired, BadTimeSignature


from totalimpactwebapp import app, util, db, login_manager, forms
from totalimpactwebapp.user import User, create_user, get_user_from_id, make_genre_heading_products
from totalimpactwebapp import views_helpers
from totalimpactwebapp.utils.unicode_helpers import to_unicode_or_bust
import newrelic.agent

logger = logging.getLogger("tiwebapp.views")
analytics.init(os.getenv("SEGMENTIO_PYTHON_KEY"), log_level=logging.INFO)















###############################################################################
#
#   CONVENIENCE FUNCTIONS
#
###############################################################################




def json_resp_from_jsonable_thing(jsonable_thing):
    json_str = json.dumps(jsonable_thing, sort_keys=True, indent=4)
    resp = make_response(json_str, 200)
    resp.mimetype = "application/json"
    return resp


def json_resp_from_thing(thing):
    """
    JSON-serialize an obj or dict and put it in a Flask response.
    This should be converted to an object and moved out of here...

    :param obj: the obj you want to serialize to json and send back
    :return: a flask json response, ready to send to client
    """

    try:
        return json_resp_from_jsonable_thing(thing)
    except TypeError:
        pass

    try:
        return json_resp_from_jsonable_thing(thing.as_dict())
    except AttributeError:
        pass

    temp_dict = thing.__dict__
    obj_dict = {}
    for k, v in temp_dict.iteritems():
        if k[0] != "_":  # we don't care to serialize private attributes

            if type(v) is datetime.datetime:  # convert datetimes to strings
                obj_dict[k] = v.isoformat()
            else:
                obj_dict[k] = v

    return json_resp_from_jsonable_thing(obj_dict)




def render_template_custom(template_name, **kwargs):
    kwargs["newrelic_footer"] = newrelic.agent.get_browser_timing_footer()
    if os.getenv("STATUS_SLOW", False) in [True, "true", "True", 1]:
        flash(
            "<strong>Performance notice:</strong> our server is currently backed up. We're fixing it now; see our <a href='http://twitter.com/impactstory_now'>status feed</a> for updates.",
            "error"
        )

    return render_template(template_name, **kwargs)


def get_user_for_response(id, request, include_products=True):
    id_type = request.args.get("id_type", "userid")

    retrieved_user = get_user_from_id(id, id_type, include_products)
    if retrieved_user is None:
        abort(404, "That user doesn't exist.")

    return retrieved_user















###############################################################################
#
#   BEFORE AND AFTER REQUESTS
#
###############################################################################



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_first_request
def setup_db_tables():
    logger.info(u"first request; setting up db tables.")
    db.create_all()




@app.before_request
def load_globals():
    g.user = current_user
    g.roots = {
        "api": os.getenv("API_ROOT"),
        "api_pretty": os.getenv("API_ROOT_PRETTY", os.getenv("API_ROOT")),
        "webapp": os.getenv("WEBAPP_ROOT"),
        "webapp_pretty": os.getenv("WEBAPP_ROOT_PRETTY", os.getenv("WEBAPP_ROOT"))
    }

    g.segmentio_key = os.getenv("SEGMENTIO_KEY")
    g.mixpanel_token = os.getenv("MIXPANEL_TOKEN")

    g.api_key = os.getenv("API_KEY")
    g.newrelic_header = newrelic.agent.get_browser_timing_header()



@app.before_request
def log_ip_address():
    if request.endpoint != "static":
        try:
            logger.info(u"{ip_address} IP address calling {method} {url}".format(
                ip_address=request.remote_addr, 
                method=request.method, 
                url=to_unicode_or_bust(request.url)))
        except UnicodeDecodeError:
            logger.debug(u"UnicodeDecodeError logging request url. Caught exception but needs fixing")


@app.before_request
def redirect_everything_but_root_and_static_and_api():
    reasons_not_to_redirect = [
        (request.path[0:4] == "/api"),
        (request.path == "/"),
        (request.path[0:7] == "/static")
    ]
    path = request.path

@app.after_request
def add_crossdomain_header(resp):
    #support CORS
    resp.headers['Access-Control-Allow-Origin'] = "*"
    resp.headers['Access-Control-Allow-Methods'] = "POST, GET, OPTIONS, PUT, DELETE"
    resp.headers['Access-Control-Allow-Headers'] = "origin, content-type, accept, x-requested-with"
    return resp


@app.template_filter('extract_filename')
def extract_filename(s):
    res = re.findall('\'([^\']*)\'', str(s))
    if res:
        return res[0].split(".")[0]
    return None





















###############################################################################
#
#   JSON VIEWS (API)
#
###############################################################################



#------------------ /user (current user using the site) -----------------


@app.route("/user/current")
def get_current_user():
    try:
        return json_resp_from_thing({"user": g.user.as_dict()})

    except AttributeError:  # anon user has no as_dict()
        return json_resp_from_thing({"user": None})


@app.route('/user/logout', methods=["POST"])
def logout():
    logout_user()
    return json_resp_from_thing({"msg": "user logged out"})


@app.route("/user/login", methods=["POST"])
def login():

    logger.debug(u"user trying to log in.")

    email = unicode(request.json["email"]).lower()
    password = unicode(request.json["password"])

    user = User.query.filter_by(email=email).first()

    if g.user is None:
        abort(404, "Email doesn't exist")
    elif not user.check_password(password):
        abort(401, "Wrong password")
    else:
        # Yay, no errors! Log the user in.
        login_user(user)


    return json_resp_from_thing({"user": user.as_dict()})


#------------------ /user/:id/about   -----------------


@app.route("/user/<profile_id>/about", methods=['GET', 'PATCH'])
def get_user_about(profile_id):

    from time import sleep
    sleep(1)

    user = get_user_for_response(
        profile_id,
        request,
        include_products=False  # returns faster this way.
    )

    if request.method == "GET":
        pass

    elif request.method == "PATCH":
        user.patch(request.json["about"])
        db.session.commit()


    return json_resp_from_thing({"about": user.as_dict()})






#------------------ user/:userId/products -----------------




@app.route("/user/<id>/products", methods=["GET", "POST", "PUT", "DELETE"])
def user_products_view_and_modify(id):

    user = get_user_for_response(id, request)

    if request.method == "GET":
        resp = user.products
        if request.args.get("include_heading_products") in [1, "true", "True"]:
            resp += make_genre_heading_products(resp)

    elif request.method == "POST":
        # you can't add/create stuff here, just refresh extant products.
        resp = user.refresh_products()

    elif request.method == "PUT":
        aliases_to_add = request.json.get("aliases")
        resp = user.add_products(aliases_to_add)

    elif request.method == "DELETE":
        tiids_to_delete = request.json.get("tiids")
        resp = user.delete_products(tiids_to_delete)

    else:
        abort(405)  # method not supported.  We shouldn't get here.

    response_to_send = json_resp_from_thing(resp)
    return response_to_send





#------------------ user/:userId/password -----------------


@app.route("/user/<email>/password", methods=["GET"])
def get_password_reset_link(email):
    email = unicode(email).lower()
    retrieved_user = User.query.filter_by(email=email).first()
    if retrieved_user is None:
        abort(404, "That user doesn't exist.")

    # make the signed reset token
    s = TimestampSigner(os.getenv("SECRET_KEY"), salt="reset-password")
    reset_token = s.sign(retrieved_user.email)

    base_reset_url = g.roots["webapp_pretty"] + "/change-password"
    full_reset_url = base_reset_url + "/" + reset_token

    # send the email here...
    mailer = mandrill.Mandrill(os.getenv("MANDRILL_APIKEY"))

    text = """Hi! You asked to reset your ImpactStory password. To do that, just
copy and paste the URL below into your browser's address
bar:\n\n{url}\n\n(If you didn't ask to reset your password, you can just ignore
this message).\nBest,\nThe ImpactStory team""".format(url=full_reset_url)

    html = """<p>Hi! You asked to reset your ImpactStory password. To do that, just
<a href="{url}">click this reset link</a>, or copy and paste the URL below into your
browser's address bar:</p><pre>{url}</pre><p>(If you didn't ask to reset your password,
you can just ignore this message.)<br>Best,<br>The ImpactStory
team</p>""".format(url=full_reset_url)

    msg = {
        "text": text,
        "html": html,
        "subject": "Password reset link",
        "from_email": "team@impactstory.org",
        "from_name": "ImpactStory support",
        "to": [{"email":email, "name":"ImpactStory user"}],  # must be a list
        "tags": ["password-resets"],
        "track_opens": False,
        "track_clicks": False
    }
    mailer.messages.send(msg)
    logger.info(u"Sent a password reset email to " + email)

    return json_resp_from_thing({"message": "link emailed."})


@app.route("/user/<id>/password", methods=["POST"])
def user_password_modify(id):
    retrieved_user = get_user_for_response(id, request)

    if  retrieved_user.check_password(request.json["currentPassword"]):
        retrieved_user.set_password(request.json["newPassword"])
        db.session.commit()
        return json_resp_from_thing({"response": "ok"})

    else:
        abort(403, "The current password is not correct.")





#------------------ user/:userId/... -----------------


@app.route("/user/<int:userId>", methods=["PUT"])
def user_put(userId):
    """
    Just a shortcut so the edit-in-place plugin can access JSON methods
    """
    method_name = "user_" + request.form["name"] + "_modify"
    return globals()[method_name](userId, request.form["value"])

@app.route("/user/<int:userId>/email")
def user_email_modify(userId, new_email):
    retrieved_user = get_user_for_response(userId)
    if g.user.get_id() != retrieved_user.get_id():
        abort(403, "You must be logged in to change your email.")

    # check for duplicates
    user_with_same_email = User.query.filter(
        func.lower(User.email) == func.lower(new_email)
    ).first()

    if user_with_same_email is None:
        pass
        retrieved_user.email = new_email
    else:
        abort(409, "Someone has already registered this email") # see http://stackoverflow.com/a/3826024/226013

    db.session.commit()
    return make_response(json.dumps(retrieved_user.email), 200)


@app.route("/user/<int:userId>/slug/<new_slug>", methods=["PUT"])
def user_slug_modify(userId, new_slug):

    # check for allowed characters
    has_non_word_chars = re.compile("[^\w'-]", re.U).search(new_slug)
    if has_non_word_chars is not None:
        abort(400, "Character not allowed.")

    # check for user login
    retrieved_user = get_user_for_response(userId)
    if g.user.get_id() != retrieved_user.get_id():
        abort(403, "You must be logged in to change your URL.")

    # check for duplicates
    user_with_same_slug = User.query.filter(
        func.lower(User.url_slug) == func.lower(new_slug)
    ).first()

    if user_with_same_slug is None:
        pass
        retrieved_user.url_slug = new_slug
    else:

        if request.args.get("fail_on_duplicate") in ["true", "yes", 1]:
            abort(409, "this url slug already exists") # see http://stackoverflow.com/a/3826024/226013
        else:
            logger.info(u"tried to mint a url slug ('{slug}') that already exists, so appending number".format(
                slug=retrieved_user.url_slug
            ))
            # to de-duplicate, mint a slug with a random number on it
            retrieved_user.uniqueify_slug()

    db.session.commit()
    return make_response(json.dumps(retrieved_user.url_slug), 200)



def user_name_modify(userId, name, name_type):
    """
    Refactored out stuff that both given and surname edits use.

    :param name_type: surname or given_name
    """

    retrieved_user = get_user_for_response(userId)
    if g.user.get_id() != retrieved_user.get_id():
        abort(403, "You must be logged in to change your name.")

    setattr(retrieved_user, name_type, name)
    db.session.commit()
    return make_response(json.dumps(name), 200)


@app.route("/user/<int:userId>/surname/<name>", methods=["PUT"])
def user_surname_modify(userId, name):
    return user_name_modify(userId, name, "surname")


@app.route("/user/<int:userId>/given_name/<name>", methods=["PUT"])
def user_given_name_modify(userId, name):
    return user_name_modify(userId, name, "given_name")




#------------------ users/test  (manage test users) -----------------


@app.route("/users/test", methods=["DELETE", "GET"])
def delete_test_user():
    coll_delete_params = {
        "include_items": "true",
        "api_admin_key": os.getenv("API_ADMIN_KEY")
    }
    if request.method == "DELETE" or request.args.get("method") == "delete":

        # for now just the first one...should be all of them
        retrieved_users = User.query.filter(User.surname == "impactstory").all()
        for user in retrieved_users:
            if user.collection_id is None:
                continue

            url = g.roots["api"] + "/v1/collection/" + user.collection_id
            r = requests.delete(url, params=coll_delete_params)
            print "delete colls and items; " + r.text

            print "deleting user ", user.email
            db.session.delete(user)

        db.session.commit()
        return make_response("deleted {num_users} users.".format(
            num_users=len(retrieved_users)))
    else:
        return make_response("these endpoint only supports deleting for now.")


@app.route("/users/test/collection_ids")
def test_user_cids():
    test_users = User.query.filter(User.surname == "impactstory").all()
    print "test_users: ", test_users
    test_collection_ids = [user.collection_id for user in test_users]
    return json_resp_from_thing({"collection_ids": test_collection_ids})






#------------------ provider/...  (proxy methods for api) -----------------

@app.route('/provider/<provider_name>/memberitems/<query_string>', methods=["GET"])
def provider_get_memberitems_proxy(provider_name, query_string):

    query = "{core_api_root}/v1/provider/{provider_name}/memberitems/{query_string}".format(
        core_api_root=g.roots["api"],
        provider_name=provider_name,
        query_string=query_string
    )
    r = requests.get(
        query,
        headers={'Content-type': 'application/json', 'Accept': 'application/json'},
        params={"api_admin_key": os.getenv("API_ADMIN_KEY")}
    )

    return json_resp_from_thing(r.json())


@app.route('/provider/<provider_name>/memberitems', methods=["POST"])
def provider_post_memberitems_proxy(provider_name):

    file = request.files['file']
    logger.debug(u"In"+provider_name+"/memberitems, got file: filename="+file.filename)
    entries_str = file.read().decode("utf-8")

    url = "{core_api_root}/v1/provider/{provider_name}/memberitems".format(
        core_api_root=g.roots["api"],
        provider_name=provider_name
    )
    r = requests.post(
        url,
        headers={'Content-type': 'application/json', 'Accept': 'application/json'},
        data=json.dumps({"descr": entries_str}),
        params={"api_admin_key": os.getenv("API_ADMIN_KEY")}
    )

    return json_resp_from_thing(r.json())




















###############################################################################
#
#   MOSTLY-STATIC PAGES
#
###############################################################################




@app.route("/<path:dummy>")  # from http://stackoverflow.com/a/14023930/226013
def redirect_to_profile(dummy):
    """
    Route things that look like user profile urls.

    *Everything* not explicitly routed to another function will end up here.
    """
    return render_template_custom('index.html')



# static pages
@app.route('/')
def index():
    return render_template_custom('index.html')


@app.route('/faq')
def faq(): 
    # get the table of items and identifiers
    which_items_loc = os.path.join(
        os.path.dirname(__file__),
        "static",
        "whichartifacts.html"
        )
    which_item_types = open(which_items_loc).read()

    # get the static_meta info for each metric
    try:
        url = "{api_root}/v1/provider?key={api_key}".format(
            api_key=g.api_key,
            api_root=g.roots["api"])
        r = requests.get(url)
        metadata = json.loads(r.text)
    except requests.ConnectionError:
        metadata = {}
    
    return render_template_custom(
        'faq.html',
        which_artifacts=which_item_types,
        provider_metadata=metadata
        )


@app.route('/api-docs')
def apidocs(): 
    return render_template_custom('api-docs.html')


@app.route("/loading.gif")
def images():
    path = "static/img/loading-small.gif"
    return send_file(path)





















###############################################################################
#
#   WIDGET STUFF
#
###############################################################################


@app.route("/embed/test/widget")
def embed_test_widget():
    return render_template_custom("test-pages/sample-embed-internal-test.html")


@app.route("/embed/impactstory.js")
@app.route("/embed/v1/impactstory.js")
def impactstory_dot_js():

    # not using render_template_custom() here, since this is a js page and is Special.
    badges_template = render_template("js-template-badges.html").replace("\n", "").replace("'", "&apos;")

    # First build the concatenated js file for the widget. Building makes a file.
    # Then open the file and put it in the template to return.
    js_widget.build() # always build this, whether dev in dev env or not
    libs = open(os.path.dirname(__file__) + "/static/js/widget.js", "r").read()

    # not using render_template_custom() here, since this is a js page and is Special.
    rendered = render_template(
        "embed/impactstory.js",
        badges_template=badges_template,
        libs=unicode(libs, "utf-8")
    )
    resp = make_response(rendered)
    """
    There is no standard way to indicate you're sending back javascript;
    This seems the most recommended one, though. See
    http://stackoverflow.com/questions/2706290/why-write-script-type-text-javascript-when-the-mime-type-is-set-by-the-serve
    and http://www.ietf.org/rfc/rfc4329.txt
     """
    resp.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return resp


@app.route("/widget-analytics", methods=['GET'])
def widget_analytics():
    d = {}
    for k, v in request.args.iteritems():
        d[k] = v

    try:
        d["hostname"] = d['url'].split("/")[2]
        d["domain"] = ".".join(d['hostname'].split(".")[-2:])  # like "impactstory.org"
    except KeyError:
        #nevermind then
        pass

    try:
        api_key = d["api-key"]
    except KeyError:
        api_key = "unknown"

    logger.info(u"got widget analytics data: {data}".format(
        data=d))

    try:
        # later look stuff up here from db, based on api-key; send along w identify() call...
        analytics.identify(user_id=api_key)
    except IndexError:
        logger.debug(u"IndexError when doing analytics.identify in widget_analytics")

    try:
        analytics.track(
            user_id=api_key,
            event="Served a page with embedded widget",
            properties=d
        )
    except IndexError:
        logger.debug(u"IndexError when doing analytics.track in widget_analytics")

    try:
        analytics.flush(async=False)  # make sure all the data gets sent to segment.io
    except IndexError:
        # sometimes the data was already flushed and we get an error popping from an empty queue
        logger.debug(u"IndexError when doing analytics.flush in widget_analytics")

    return make_response(request.args.get("callback", "") + '({"status": "success"})', 200)



@app.route('/admin/key')
def generate_api_key():
    return render_template_custom('generate-api.html')

@app.route('/logo')
def logo():
    filename = "static/img/logos/impactstory-logo-big.png"
    return send_file(filename, mimetype='image/png')


