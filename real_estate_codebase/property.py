from dbconnection import MySQLConnection
from transaction import Transaction

class Property:

    def __init__(self):
        self.db = MySQLConnection()
        self.p_id = self._fetch_max_p_id()

    def _fetch_max_p_id(self):
        """
        Fetches the highest p_id using an SQL function.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT GetMaxPropertyId() AS max_id"  # Call the SQL function
            cursor.execute(query)
            result = cursor.fetchone()
            # Ensure result is correctly handled
            return result[0] if result and result[0] is not None else 100
        except Exception as e:
            print(f"Error fetching max property ID: {e}")
            return 100  # Default value if error occurs
        finally:
            self.db.disconnect()

    def get_p_id(self):
        return self.p_id

    def add_property(self, p_type, p_size, p_price, p_status, agent_id):
        """
        Adds a new property to the database.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()

            # Fetch the latest p_id from the database
            query_max_id = "SELECT GetMaxPropertyId() AS max_id"
            cursor.execute(query_max_id)
            result = cursor.fetchone()
            current_max_id = result[0] if result and result[0] is not None else 100

            # Increment the p_id for the new property
            new_p_id = current_max_id + 1

            # Insert the new property
            query_insert = """
            INSERT INTO Property (p_id, p_type, p_size, p_price, p_status, agent_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (new_p_id, p_type, p_size, p_price, p_status, agent_id))
            self.db.connection.commit()
            print("Property added successfully!")
        except Exception as e:
            print(f"Error adding property: {e}")
        finally:
            self.db.disconnect()

    def modify_property(self, p_id, new_price, new_type):
        """
        Modifies the price and type of a property while restricting changes to
        properties with status 'sold', as well as size and ID.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()

            # Check if the property status is 'sold'
            status_check_query = "SELECT p_status FROM Property WHERE p_id = %s"
            cursor.execute(status_check_query, (p_id,))
            result = cursor.fetchone()

            if result and result[0] == 'sold':
                print("Error: Cannot modify a property with status 'sold'.")
                return "Error: Cannot modify a property with status 'sold'."

            # Proceed with the modification if not sold
            query = """
            UPDATE Property 
            SET p_price = %s, p_type = %s
            WHERE p_id = %s
            """
            cursor.execute(query, (new_price, new_type, p_id))
            self.db.connection.commit()
            print("Property modified successfully!")
            return "Property modified successfully!"
        except Exception as e:
            print(f"Error modifying property: {e}")
            return f"Error modifying property: {e}"
        finally:
            self.db.disconnect()

    def sell_property(self, p_id, sold_price, agent_id, client_username):
        """
        Marks a property as sold and associates the sale with a transaction.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()

            # Check if property is available
            query_status = "SELECT p_status FROM Property WHERE p_id = %s"
            cursor.execute(query_status, (p_id,))
            result = cursor.fetchone()

            if not result or result[0] == 'sold':
                return "The property is already sold or does not exist."

            # Update the property status and price
            update_query = """
            UPDATE Property 
            SET p_status = 'sold', p_price = %s
            WHERE p_id = %s AND agent_id = %s
            """
            cursor.execute(update_query, (sold_price, p_id, agent_id))
            self.db.connection.commit()

            # Calculate commission
            commission_rate = 0.05
            commission = sold_price * commission_rate

            # Insert into Transactions table
            insert_transaction_query = """
            INSERT INTO Transactions (t_id, commision, t_date, c_username, p_id, agent_id)
            VALUES (NULL, %s, NOW(), %s, %s, %s)
            """
            cursor.execute(insert_transaction_query, (commission, client_username, p_id, agent_id))
            self.db.connection.commit()

            return "Property sold and transaction recorded successfully!"
        except Exception as e:
            return f"Error selling property: {e}"
        finally:
            self.db.disconnect()

    def view_property(self, price_range=None, size_range=None, p_type=None):
        """
        Views properties with optional filters for price range, size range, and type.
        Utilizes a SQL stored procedure for database query execution.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor(dictionary=True)

            # Prepare parameters for the stored procedure
            min_price = price_range[0] if price_range and len(price_range) == 2 else None
            max_price = price_range[1] if price_range and len(price_range) == 2 else None
            min_size = size_range[0] if size_range and len(size_range) == 2 else None
            max_size = size_range[1] if size_range and len(size_range) == 2 else None

            # Call the stored procedure
            cursor.callproc('GetProperties', (min_price, max_price, min_size, max_size, p_type))

            # Fetch results from the procedure
            results = cursor.stored_results()
            properties = []
            for result in results:
                properties.extend(result.fetchall())

            return properties
        except Exception as e:
            print(f"Error viewing properties: {e}")
            return []
        finally:
            self.db.disconnect()

    def filter_properties(self, agent_id, price_min=None, price_max=None, size_min=None, size_max=None,
                          property_type=None):
        """
        Filters properties based on the given criteria: price range, size range, property type,
        and ensures only properties assigned to the logged-in agent are retrieved.
        Utilizes a SQL stored procedure for database query execution.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor(dictionary=True)

            # Call the stored procedure
            cursor.callproc('FilterProperties', (agent_id, price_min, price_max, size_min, size_max, property_type))

            # Fetch results from the procedure
            results = cursor.stored_results()
            properties = []
            for result in results:
                properties.extend(result.fetchall())
            return properties
        except Exception as e:
            print(f"Error filtering properties: {e}")
            return []
        finally:
            self.db.disconnect()


