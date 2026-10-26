"""
Load test of the public read path (what anonymous visitors hit hardest).

    locust -f loadtest/locustfile.py --host http://127.0.0.1:5050 --headless -u 200 -r 20 -t 60s
"""
import random

from locust import HttpUser, between, task

CITIES = ["Lisbon", "Paris", "New York", "Tokyo", "London", "Austin", "Dubai", "Berlin", "Toronto", "Bali"]
MODES = ["short_term_stay", "long_term_rent", "sale"]
SORTS = ["newest", "price_asc", "price_desc", "rating"]


class Visitor(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        r = self.client.get("/api/v1/listings?limit=24", name="/listings (home)")
        self.ids = [i["public_id"] for i in r.json()["items"]] if r.ok else []

    @task(5)
    def search_city(self):
        mode, sort, city = random.choice(MODES), random.choice(SORTS), random.choice(CITIES)
        query = f"mode={mode}&city={city}&sort={sort}"
        r = self.client.get(f"/api/v1/listings?{query}", name="/listings?city")
        if r.ok and r.json()["items"]:
            self.ids = [i["public_id"] for i in r.json()["items"]]
            cursor = r.json()["next_cursor"]
            if cursor and random.random() < 0.4:
                self.client.get(f"/api/v1/listings?{query}&cursor={cursor}", name="/listings?cursor")

    @task(3)
    def search_map(self):
        lat, lng = random.choice([(40.73, -73.99), (48.86, 2.35), (38.72, -9.14), (51.5, -0.12)])
        self.client.get(f"/api/v1/listings?bbox={lat - .05},{lng - .07},{lat + .05},{lng + .07}", name="/listings?bbox")

    @task(2)
    def search_text(self):
        self.client.get(f"/api/v1/listings?q={random.choice(['garden', 'cozy view', 'waterfront', 'loft'])}",
                        name="/listings?q")

    @task(4)
    def listing_detail(self):
        if self.ids:
            self.client.get(f"/api/v1/listings/{random.choice(self.ids)}", name="/listings/:id")

    @task(1)
    def destinations(self):
        self.client.get("/api/v1/destinations")
