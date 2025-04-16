from datetime import datetime
from dbconnection import MySQLConnection

class Transaction:
    def __init__(self):
        self.db = MySQLConnection()

    def update_transaction_table(self, c_username, p_id, agent_id):
        """
        Updates the Transactions table with a new transaction record.
        Fetches commission data from the TransactionLog table.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()

            # Retrieve commission from TransactionLog
            query_commission = "SELECT commision FROM TransactionLog WHERE p_id = %s"
            cursor.execute(query_commission, (p_id,))
            result = cursor.fetchone()

            if not result:
                return "Error: Commission data not found in TransactionLog. Transaction aborted."

            commission = result[0]

            # Insert the transaction record
            query_insert_transaction = """
            INSERT INTO Transactions (t_id, commision, t_date, c_username, p_id, agent_id)
            VALUES ((SELECT IFNULL(MAX(t_id), 0) + 1 FROM Transactions), %s, NOW(), %s, %s, %s)
            """
            cursor.execute(query_insert_transaction, (commission, c_username, p_id, agent_id))
            self.db.connection.commit()

            return "Transaction recorded successfully!"
        except Exception as e:
            return f"Error updating transaction table: {e}"
        finally:
            self.db.disconnect()
