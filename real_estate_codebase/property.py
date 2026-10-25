from dbconnection import get_connection


def _call(cursor, procedure, args):
    cursor.callproc(procedure, args)
    rows = []
    for result in cursor.stored_results():
        rows.extend(result.fetchall())
    return rows


class Property:

    def add_property(self, p_type, p_size, p_price, agent_id):
        """
        Adds a new available property owned by the agent. p_id comes from AUTO_INCREMENT.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            query = """
            INSERT INTO Property (p_type, p_size, p_price, p_status, agent_id)
            VALUES (%s, %s, %s, 'available', %s)
            """
            cursor.execute(query, (p_type, p_size, p_price, agent_id))
            connection.commit()
            return cursor.lastrowid

    def modify_property(self, p_id, new_price, new_type, agent_id):
        """
        Updates price and type of an unsold property, only if it belongs to `agent_id`.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            query = """
            UPDATE Property
            SET p_price = %s, p_type = %s
            WHERE p_id = %s AND agent_id = %s AND p_status <> 'sold'
            """
            cursor.execute(query, (new_price, new_type, p_id, agent_id))
            connection.commit()
            if cursor.rowcount == 0:
                return "Property not found, not yours, or already sold."
            return "Property modified successfully!"

    def sell_property(self, p_id, sold_price, agent_id, client_username):
        """
        Sells a property through the CompleteSale stored procedure, which updates the
        property and records the transaction atomically (one DB transaction).
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.callproc('CompleteSale', (p_id, agent_id, client_username, sold_price))
                connection.commit()
                return "Property sold and transaction recorded successfully!"
            except Exception as e:
                connection.rollback()
                # SIGNAL messages from the procedure are safe to show
                return getattr(e, "msg", "Error selling property.")

    def view_property(self, price_min=None, price_max=None, size_min=None, size_max=None, p_type=None):
        """
        Public property search via the GetProperties stored procedure.
        """
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            return _call(cursor, 'GetProperties', (price_min, price_max, size_min, size_max, p_type))

    def filter_properties(self, agent_id, price_min=None, price_max=None, size_min=None, size_max=None,
                          property_type=None):
        """
        The logged-in agent's own properties via the FilterProperties stored procedure.
        """
        with get_connection() as connection:
            cursor = connection.cursor(dictionary=True)
            return _call(cursor, 'FilterProperties',
                         (agent_id, price_min, price_max, size_min, size_max, property_type))
