from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from client import Client
from agent import Agent
from property import Property
import os
import subprocess

app = Flask(__name__)
app.secret_key = "your_secret_key"

client = Client()
agent = Agent()
property_instance =  Property()

@app.route('/')
def main_page():
    return render_template('main_page.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_info = client.load_client_info(username)
        if user_info and user_info['c_password'] == password:
            flash('Login successful!', 'success')
            return redirect(url_for('client_main_page')) # change this to the page where properties will be shown
        else:
            flash('Invalid username or password!', 'error')
    return render_template('./client_login/client_login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        contact = request.form['contact']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        postal_code = request.form['postal_code']

        if client.check_username(username):
            client.register_client(name, username, password, contact, postal_code, city, street, state)
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already taken!', 'error')
    return render_template('./client_login/client_signup.html')


@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        contact = request.form.get('contact')

        # Check if the username exists in the system
        if not client.check_username(username):
            client.forgot_password(new_password, username, contact)
            return redirect(url_for('login'))
        else:
            flash('Username or contact incorrect. Try Again')
            return redirect(url_for('forgotpassword'))

    # For GET requests, render the forgot password template
    return render_template('./client_login/client_forgotpassword.html')

@app.route('/agent', methods=['GET', 'POST'])
def agent_login():
    if request.method == 'POST':
        agent_id = request.form['Agent ID']
        password = request.form['password']

        agent_info = agent.load_agent_login_info(agent_id)
        if agent_info and agent_info['agent_password'] == password:
            # Store agent ID in session
            session['agent_id'] = agent_id
            flash('Login successful!', 'success')
            return redirect(url_for('agent_main_page'))  # No need to pass agent_id directly
        else:
            flash('Invalid AgentID or password!', 'error')
    return render_template('./agent_login/agent_login.html')

@app.route('/agentsignup', methods=['GET', 'POST'])
def agent_signup():
    if request.method == 'POST':
        agent_name = request.form['agent_name']
        agent_password = request.form['password']
        agent_contact = request.form['contact']

        # Register the new agent
        try:
            # Generate a unique Agent ID
            agent_id = agent.get_agent_id()
            agent.register_agent(agent_name, agent_password, agent_contact)

            # Inform the user of their Agent ID
            flash(f'Registration successful! Your Agent ID is {agent_id}', 'success')
            return redirect(url_for('agent_login'))
        except Exception as e:
            flash(f'Error during registration: {e}', 'error')
            return redirect(url_for('agent_signup'))

    # Generate agent ID for GET requests (optional, to display before submission)
    agent_id = agent.get_agent_id()
    return render_template('./agent_login/agent_signup.html', agent_id=agent_id)

@app.route('/agent_forgotpassword', methods=['GET', 'POST'])
def agent_forgotpassword():
    if request.method == 'POST':
        agent_id = request.form.get('agent_id')
        new_password = request.form.get('password')
        contact = request.form.get('contact')

        # Check if the username exists in the system
        if not agent.check_agentid(agent_id):
            agent.forgot_password(new_password, agent_id, contact)
            return redirect(url_for('agent_login'))
        else:
            flash('AgentID or contact incorrect. Try Again')
            return redirect(url_for('agent_forgotpassword'))

    # For GET requests, render the forgot password template
    return render_template('./agent_login/agent_forgotpassword.html')

@app.route('/client_mainpage', methods=['GET'])
def client_main_page():
    # Retrieve filter parameters from the query string
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    size_min = request.args.get('size_min', type=float)
    size_max = request.args.get('size_max', type=float)
    property_type = request.args.get('property_type', type=str)

    # Prepare filter conditions
    price_range = (price_min, price_max) if price_min is not None and price_max is not None else None
    size_range = (size_min, size_max) if size_min is not None and size_max is not None else None

    # Fetch properties using the Property class
    properties = property_instance.view_property(
        price_range=price_range,
        size_range=size_range,
        p_type=property_type
    )

    # Render the template with the filtered properties
    return render_template('client_main_page.html', properties=properties or [])

@app.route('/client_logout')
def client_logout():
    """
    Logs out the user and redirects to the login page.
    """
    # Add any session clearing logic if using Flask-Login or sessions
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('login'))

@app.route('/agent_main_page', methods=['GET', 'POST'])
def agent_main_page():
    """
    Displays the main page for an agent, showing all available properties or filtered results.
    """
    try:
        # Check if agent_id is in the session
        agent_id = session.get('agent_id')
        if not agent_id:
            flash("You need to log in first.", "error")
            return redirect(url_for('agent_login'))

        # Get filter parameters from the form submission (for POST) or query string (for GET)
        price_min = request.form.get('price_min', type=float)
        price_max = request.form.get('price_max', type=float)
        size_min = request.form.get('size_min', type=float)
        size_max = request.form.get('size_max', type=float)
        property_type = request.form.get('property_type', type=str)

        # Fetch properties based on filters and agent_id
        filtered_properties = property_instance.filter_properties(
            agent_id=agent_id,
            price_min=price_min,
            price_max=price_max,
            size_min=size_min,
            size_max=size_max,
            property_type=property_type
        )

        # Render the agent main page with filtered properties
        return render_template(
            'agent_main_page.html',
            agent_id=agent_id,
            properties=filtered_properties
        )
    except Exception as e:
        flash(f"Error loading properties: {e}", "error")
        return redirect(url_for('agent_login'))


@app.route('/agent_logout')
def agent_logout():
    """
    Logs out the agent and redirects to the login page.
    """
    session.pop('agent_id', None)  # Remove agent_id from session
    flash('You have been logged out successfully!', 'info')
    return redirect(url_for('agent_login'))

@app.route('/add_property', methods=['POST'])
def add_property():
    """
    Handles the addition of a property by the logged-in agent.
    Automatically uses the agent_id from the session.
    """
    if 'agent_id' not in session:
        flash("You must be logged in to add properties.", "error")
        return redirect(url_for('agent_login'))

    try:
        # Retrieve agent_id from session
        agent_id = session['agent_id']

        # Get property details from the form
        p_type = request.form['p_type']
        p_size = float(request.form['p_size'])
        p_price = float(request.form['p_price'])
        p_status = request.form['p_status']

        # Call the Property class method
        property_instance.add_property(p_type, p_size, p_price, p_status, agent_id)

        flash("Property added successfully!", "success")
    except Exception as e:
        flash(f"Error adding property: {e}", "error")

    return redirect(url_for('agent_main_page'))

@app.route('/modify_property', methods=['POST'])
def modify_property():
    """
    Modifies the details of a property (price and type) using the Property class.
    """
    if 'agent_id' not in session:
        flash("You must be logged in to modify properties.", "error")
        return redirect(url_for('agent_login'))

    try:
        # Retrieve property details from the form
        p_id = request.form['p_id']
        new_type = request.form['p_type']
        new_price = float(request.form['p_price'])

        # Call the modify_property method
        property_instance.modify_property(p_id, new_price, new_type)

        flash("Property modified successfully!", "success")
    except Exception as e:
        flash(f"Error modifying property: {e}", "error")

    return redirect(url_for('agent_main_page'))

@app.route('/sell_property', methods=['POST'])
def sell_property():
    """
    Sells a property and uses the Transaction class to update the Transactions table.
    """
    if 'agent_id' not in session:
        flash("You must be logged in to sell properties.", "error")
        return redirect(url_for('agent_login'))

    try:
        # Retrieve form data
        p_id = request.form['p_id']
        selling_price = float(request.form['selling_price'])
        client_username = request.form['client_username']
        agent_id = session['agent_id']

        # Call the sell_property method
        result = property_instance.sell_property(p_id, selling_price, agent_id, client_username)
        flash(result, "success" if "successfully" in result else "error")
    except Exception as e:
        flash(f"Error selling property: {e}", "error")

    return redirect(url_for('agent_main_page'))

@app.route('/backup', methods=['GET'])
def backup_database():
    """
    Creates a backup of the 'real_estate' database and provides it as a downloadable file.
    """
    try:
        # Database credentials
        db_host = "localhost"  # Replace with your database host
        db_user = "root"       # Replace with your database user
        db_password = "root1234"  # Replace with your database password
        db_name = "real_estate"  # Replace with your database name

        # Backup file path
        backup_file = f"{db_name}_backup.sql"

        # mysqldump command
        command = [
            "mysqldump",
            f"--host={db_host}",
            f"--user={db_user}",
            f"--password={db_password}",
            db_name
        ]

        # Create the backup
        with open(backup_file, "w") as output_file:
            subprocess.run(command, stdout=output_file, check=True)

        # Send the backup file to the user
        return send_file(backup_file, as_attachment=True)
    except subprocess.CalledProcessError as e:
        flash(f"Error creating database backup: {e}", "error")
        return redirect(url_for('main_page'))
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "error")
        return redirect(url_for('main_page'))

if __name__ == '__main__':
    app.run(debug=True)
