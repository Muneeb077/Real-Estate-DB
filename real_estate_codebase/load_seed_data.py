"""
Loads the dummy CSVs into the database, hashing the agent passwords with Argon2id
on the way in. Run once after real_estate.sql:  python load_seed_data.py
"""
import csv
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from dbconnection import get_connection
from passwords import hash_password

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def main():
    with open(os.path.join(ROOT, "Dummy_Agent_Data.csv")) as f:
        agents = [(int(r["agent_id"]), r["agent_name"], hash_password(r["agent_password"]), r["agent_contact"])
                  for r in csv.DictReader(f)]
    with open(os.path.join(ROOT, "Dummy_Property_Data_with_Agent_IDs.csv")) as f:
        properties = [(int(r["p_id"]), r["p_type"], int(r["p_size"]), r["p_price"], r["p_status"],
                       int(r["agent_id"])) for r in csv.DictReader(f)]

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.executemany("INSERT INTO Agent (agent_id, agent_name, agent_password, agent_contact) "
                           "VALUES (%s, %s, %s, %s)", agents)
        cursor.executemany("INSERT INTO Property (p_id, p_type, p_size, p_price, p_status, agent_id) "
                           "VALUES (%s, %s, %s, %s, %s, %s)", properties)
        connection.commit()
    print(f"Loaded {len(agents)} agents and {len(properties)} properties.", file=sys.stderr)


if __name__ == "__main__":
    main()
