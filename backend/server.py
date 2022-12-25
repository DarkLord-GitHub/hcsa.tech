import pathlib
from sanic import Sanic, response
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from google.oauth2 import id_token
import jwt
import uuid
import json
import os
import aiohttp
import copy

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "./client_secret.json")
config = json.load(open(os.path.join(pathlib.Path(__file__).parent, "./config.json")))

flow = Flow.from_client_secrets_file(client_secrets_file=client_secrets_file,
                                     scopes=["https://www.googleapis.com/auth/userinfo.profile",
                                             "https://www.googleapis.com/auth/userinfo.email",
                                             "openid"],
                                     redirect_uri="https://api.hcsa.tech/callback" if config["production"]
                                     else "http://localhost:8000/callback")

app = Sanic(config["name"])


async def revoke_token(token):
    async with aiohttp.ClientSession() as session:
        async with session.post("https://oauth2.googleapis.com/revoke", data={"token": token}) as resp:
            return await resp.json()


@app.middleware("response")
async def cors(request, resp):
    resp.headers.update({"Access-Control-Allow-Origin": "*"})


@app.listener("before_server_start")
async def setup(app_, loop):
    app_.ctx.sessions = {}


app.register_listener(setup, "before_server_start")


@app.route("/login")
async def login(request):
    authorization_url, state = flow.authorization_url()
    resp = response.redirect(authorization_url)
    resp.cookies["state"] = state
    resp.cookies["state"]["httponly"] = False

    # what type of cookie should I use for state?
    return resp  # &hd=fcpsschools.net


@app.route("/callback")
async def callback(request):
    flow.fetch_token(authorization_response=request.url)

    cookie = request.cookies.get("state")

    if not cookie or not cookie == request.args.get("state"):
        # return response.redirect(config["frontend_url"] + "/state_mismatch")
        return response.json({"error": "state mismatch",
                              "State was": request.cookies.get("state"),
                              "and was supposed to be ": request.args.get("state")})

    credentials = flow.credentials
    token_request = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(id_token=credentials._id_token, request=token_request,
                                           audience=credentials.client_id)
    await revoke_token(credentials.token)

    uuid_ = str(uuid.uuid4())
    email = id_info["email"]
    jwt_token = jwt.encode({"email": email, "session": uuid_}, config["secret"], algorithm="HS256")
    if email not in app.ctx.sessions:
        app.ctx.sessions[email] = {
            "firstName": id_info["given_name"],
            "lastName": id_info["family_name"],
            "email": email,
            "picture": id_info["picture"],
            "sessions": {
                uuid_: {
                    "ip": request.ip,
                    "User-Agent": request.headers.get("User-Agent"),
                }
            }
        }
    else:
        app.ctx.sessions[email]["sessions"][uuid_] = {
            "ip": request.ip,
            "User-Agent": request.headers.get("User-Agent"),
        }

    return response.redirect(config["frontend_url"] + "/callback?session=" + jwt_token)


@app.route("/user")
async def user(request):
    # return json with firstName, lastName, email, and picture
    session = request.args.get("session")
    # decode session and get the uuid, and check if it is a a valid jwt token
    try:
        session = jwt.decode(session, config["secret"], algorithms=["HS256"])
    except jwt.exceptions.InvalidSignatureError:
        return response.json({"success": False, "error": "invalid session, invalid signature"})

    # check if the uuid is in the sessions
    if session["email"] not in app.ctx.sessions or \
            session["session"] not in app.ctx.sessions[session["email"]]["sessions"]:
        return response.json(
            {"success": False, "error": "invalid session, session not found, report this asap for $$$"})

    data = copy.deepcopy(app.ctx.sessions[session["email"]])
    del data["sessions"]
    data["success"] = True
    return response.json(data)


@app.route("/user/sessions")
async def user_sessions(request):
    # return json of all sessions without the token
    session = request.args.get("session")
    # decode session and get the uuid, and check if it is a a valid jwt token
    try:
        session = jwt.decode(session, config["secret"], algorithms=["HS256"])
    except jwt.exceptions.InvalidSignatureError:
        return response.json({"success": False, "error": "invalid session, invalid signature"})
    # check if the uuid is in the sessions
    if session["email"] not in app.ctx.sessions or \
            session["session"] not in app.ctx.sessions[session["email"]]["sessions"]:
        return response.json(
            {"success": False, "error": "invalid session, session not found, report this asap for $$$"})
    return response.text(json.dumps(app.ctx.sessions[session["email"]]["sessions"], indent=4))


@app.route("/logout", methods=["POST"])
async def logout(request):
    session_id = request.args.get("session")
    try:
        session = jwt.decode(session_id, config["secret"], algorithms=["HS256"])
    except jwt.exceptions.InvalidSignatureError:
        return response.json({"success": False})

    if session["email"] not in app.ctx.sessions or \
            session["session"] not in app.ctx.sessions[session["email"]]["sessions"]:
        return response.json({"success": False})

    # revoke the token
    del app.ctx.sessions[session["email"]]["sessions"][session["session"]]
    return response.json({"success": True})


@app.route("/")
async def index(request):
    return response.redirect(config["frontend_url"])


@app.route("/favicon.ico")
async def favicon(request):
    return await response.file(os.path.join(pathlib.Path(__file__).parent, "./favicon.ico"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, fast=config["production"], debug=True)
