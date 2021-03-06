__author__ = 'Colin'


import logging

from backend.database import DB


logger = logging.getLogger("savvy.models.prices")


class PriceDB(DB):
    """Class to connect to the Prices Datastore."""

    def price_stats(self, product_id):
        """Returns the average price of a product."""
        result = self.db.prices.aggregate([
            {
                "$match":
                {
                    "product_id": product_id
                }
            },
            {
                "$group":
                {
                    "_id": "$product_id",
                    "average_price": {"$avg": "$price"},
                    "lowest_price": {"$min": "$price"},
                    "highest_price": {"$max": "$price"}
                }
            }
        ])
        try:
            stats = result.next()
            stats["average_price"] = int(stats["average_price"])
            stats["lowest_price"] = int(stats["lowest_price"])
            stats["highest_price"] = int(stats["highest_price"])
            logger.debug("Retrieved price stats for '{}' = {}".format(product_id, stats))
        except StopIteration:
            logger.warning("Unable to retrieve average price for '{}'".format(product_id))
            return {
                "average_price": -1,
                "lowest_price": -1,
                "highest_price": -1
            }
        return stats

    def average_price_per_day(self, product_id):
        """Returns an x,y coordinate for a product per day."""
        result = self.db.prices.aggregate([
            {
                "$match":
                {
                    "product_id": product_id
                }
            },
            {
                "$project": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$submitted_timestamp"}},
                    "price": 1
                }
            },
            {
                "$group":
                {
                    "_id": {"date": "$date"},
                    "y": {"$avg": "$price"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "x": "$_id.date",
                    "y": 1
                }
            }
        ])
        try:
            average_price_per_day = list(result)
            logger.debug("Retrieved average price per day for '{}'".format(product_id))
            logger.debug(average_price_per_day)
        except StopIteration:
            logger.warning("Unable to retrieve average price per day for '{}'".format(product_id))
            average_price_per_day = []
        average_price_per_day = [[price["x"], int(price["y"])] for price in average_price_per_day]
        return average_price_per_day

    def get_sanitized_submissions(self, *args, **kwargs):
        submissions = []
        for submission in self.get_submissions(*args, **kwargs):
            submission.pop("user", None)
            submissions.append(submission)
        return submissions

    def get_submissions(self, product_id=None, business_id=None, user_id=None, limit=None, most_recent=False):
        """Returns a list of matching prices."""
        from backend.models.businesses import BusinessDB
        query = {}
        if product_id:
            query["product_id"] = product_id
        if business_id:
            query["business_id"] = business_id
        if user_id:
            query["user_id"] = user_id
        pipeline = [
            {
                "$match": query
            }
        ]
        if most_recent:
            pipeline.append({"$sort": {"submitted_timestamp": -1}})
        if limit:
            pipeline.append({"$limit": limit})
        result = self.db.prices.aggregate(pipeline)
        try:
            results = list(result)
            logger.debug("Retrieved average price per day for '{}'".format(product_id))
        except StopIteration:
            logger.warning("Unable to retrieve average price per day for '{}'".format(product_id))
            results = []
        submissions = []
        business_db = BusinessDB()
        for submission in results:
            submission["price_id"] = str(submission.pop("_id"))
            submission["submitted_timestamp"] = str(submission["submitted_timestamp"].as_datetime())
            submission["business_details"] = business_db.get_business(business_id=submission.pop("business_id"))
            submissions.append(submission)
        return submissions

    def add_price(self, product, business, price, user_id, image):
        """Adds a price record to the database."""
        from bson.timestamp import Timestamp
        from datetime import datetime
        from backend.auth import current_user
        from backend.models.businesses import BusinessDB
        from backend.models.products import ProductDB
        from backend.utils import get_google_places_by_id

        # Add product and tags to DB
        product_db = ProductDB()
        product_id = product_db.add_product(description=product["description"],
                                            tags=product["tags"])

        if isinstance(business, str):
            business = get_google_places_by_id(business)

        # Add business to database
        business_db = BusinessDB()
        business_id = business_db.add_business(name=business["name"],
                                               address=business["formatted_address"],
                                               phone_number=business["formatted_phone_number"],
                                               google_places=business)

        new_price = {"product_id": product_id,
                     "business_id": business_id,
                     "price": int(price),
                     "user_id": user_id,
                     "submitted_timestamp": Timestamp(datetime.now(), 1),
                     "image": image}
        result = self.db.prices.insert_one(new_price)
        return result.inserted_id or None

