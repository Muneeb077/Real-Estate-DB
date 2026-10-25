import logging
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

load_dotenv()

from client import Client
from agent import Agent
from property import Property

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"))
log = logging.getLogger(__name__)

client = Client()
agent = Agent()
property_instance = Property()


def agent_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if 'agent_id' not in session:
            flash("You need to log in first.", "error")
            return redirect(url_for('agent_login'))
        return view(*args, **kwargs)
    return wrapper


def _float_arg(source, name):
    return source.get(name, type=float)


@app.route('/')
def main_page():
    return render_template('main_page.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if client.authenticate(username, password):
            session.clear()
            session['client_username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('client_main_page'))
        flash('Invalid username or password!', 'error')
    return render_template('./client_login/client_login.html')


@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        if client.check_username(username):
            client.register_client(
                request.form['name'], username, request.form['password'], request.form['contact'],
                request.form['postal_code'], request.form['city'], request.form['street'], request.form['state'],
            )
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        flash('Username already taken!', 'error')
    return render_template('./client_login/client_signup.html')


@app.route('/forgotpassword', methods=['GET', 'POST'])
@limiter.limit("3 per hour", methods=["POST"])
def forgotpassword():
    if request.method == 'POST':
        if client.forgot_password(request.form.get('new_password'), request.form.get('username'),
                                  request.form.get('contact')):
            flash('Password reset. You can now log in.', 'success')
            return redirect(url_for('login'))
        flash('Username or contact incorrect. Try Again', 'error')
        return redirect(url_for('forgotpassword'))
    return render_template('./client_login/client_forgotpassword.html')


@app.route('/agent', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def agent_login():
    if request.method == 'POST':
        agent_id = request.form['Agent ID']
        if agent.authenticate(agent_id, request.form['password']):
            session.clear()
            session['agent_id'] = int(agent_id)
            flash('Login successful!', 'success')
            return redirect(url_for('agent_main_page'))
        flash('Invalid AgentID or password!', 'error')
    return render_template('./agent_login/agent_login.html')


@app.route('/agentsignup', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def agent_signup():
    if request.method == 'POST':
        try:
            agent_id = agent.register_agent(request.form['agent_name'], request.form['password'],
                                            request.form['contact'])
            flash(f'Registration successful! Your Agent ID is {agent_id}', 'success')
            return redirect(url_for('agent_login'))
        except Exception:
            log.exception("Agent registration failed")
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('agent_signup'))
    return render_template('./agent_login/agent_signup.html')


@app.route('/agent_forgotpassword', methods=['GET', 'POST'])
@limiter.limit("3 per hour", methods=["POST"])
def agent_forgotpassword():
    if request.method == 'POST':
        if agent.forgot_password(request.form.get('password'), request.form.get('agent_id'),
                                 request.form.get('contact')):
            flash('Password reset. You can now log in.', 'success')
            return redirect(url_for('agent_login'))
        flash('AgentID or contact incorrect. Try Again', 'error')
        return redirect(url_for('agent_forgotpassword'))
    return render_template('./agent_login/agent_forgotpassword.html')


@app.route('/client_mainpage', methods=['GET'])
def client_main_page():
    """
    Public listing page: anyone can browse, no account needed.
    """
    properties = property_instance.view_property(
        price_min=_float_arg(request.args, 'price_min'),
        price_max=_float_arg(request.args, 'price_max'),
        size_min=_float_arg(request.args, 'size_min'),
        size_max=_float_arg(request.args, 'size_max'),
        p_type=request.args.get('property_type') or None,
    )
    return render_template('client_main_page.html', properties=properties)


@app.route('/client_logout')
def client_logout():
    session.pop('client_username', None)
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('login'))


@app.route('/agent_main_page', methods=['GET', 'POST'])
@agent_required
def agent_main_page():
    """
    Displays the logged-in agent's properties, optionally filtered.
    """
    properties = property_instance.filter_properties(
        agent_id=session['agent_id'],
        price_min=_float_arg(request.form, 'price_min'),
        price_max=_float_arg(request.form, 'price_max'),
        size_min=_float_arg(request.form, 'size_min'),
        size_max=_float_arg(request.form, 'size_max'),
        property_type=request.form.get('property_type') or None,
    )
    return render_template('agent_main_page.html', agent_id=session['agent_id'], properties=properties)


@app.route('/agent_logout')
def agent_logout():
    session.pop('agent_id', None)
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('agent_login'))


@app.route('/add_property', methods=['POST'])
@agent_required
def add_property():
    try:
        property_instance.add_property(request.form['p_type'], float(request.form['p_size']),
                                       float(request.form['p_price']), session['agent_id'])
        flash("Property added successfully!", "success")
    except Exception:
        log.exception("Add property failed")
        flash("Error adding property.", "error")
    return redirect(url_for('agent_main_page'))


@app.route('/modify_property', methods=['POST'])
@agent_required
def modify_property():
    try:
        result = property_instance.modify_property(request.form['p_id'], float(request.form['p_price']),
                                                   request.form['p_type'], session['agent_id'])
        flash(result, "success" if "successfully" in result else "error")
    except Exception:
        log.exception("Modify property failed")
        flash("Error modifying property.", "error")
    return redirect(url_for('agent_main_page'))


@app.route('/sell_property', methods=['POST'])
@agent_required
def sell_property():
    try:
        result = property_instance.sell_property(request.form['p_id'], float(request.form['selling_price']),
                                                 session['agent_id'], request.form['client_username'])
        flash(result, "success" if "successfully" in result else "error")
    except Exception:
        log.exception("Sell property failed")
        flash("Error selling property.", "error")
    return redirect(url_for('agent_main_page'))


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
