import json


class Promotion:
    def __init__(self, promotion_code: str, promotion_title: str, promotion_url: str, product_url: str):
        self.promotion_code = promotion_code
        self.promotion_title = promotion_title
        self.promotion_url = promotion_url
        self.product_url = product_url

    def to_json(self):
        json_object = {
            "promotion_code": self.promotion_code,
            "promotion_title": self.promotion_title,
            "promotion_url": self.promotion_url,
            "product_url": self.product_url
        }
        return json.dumps(json_object, indent=2)

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.__str__()


class ProductDetails:
    def __init__(self, promotion_code: str, promotion_title: str, promotion_url: str, product_url: str,
                 product_title: str, product_image_url: str, product_price: str, product_sales: int, product_asin: str):
        self.id = f"{product_asin}/{promotion_code}"
        self.promotion_code = promotion_code
        self.promotion_title = promotion_title
        self.promotion_url = promotion_url
        self.product_url = product_url
        self.product_title = product_title
        self.product_image_url = product_image_url
        self.product_price = product_price
        self.product_sales = product_sales
        self.product_asin = product_asin

    def to_json(self):
        json_object = {
            'id': self.id,
            "promotion_code": self.promotion_code,
            "promotion_title": self.promotion_title,
            "promotion_url": self.promotion_url,
            "product_url": self.product_url,
            "product_title": self.product_title,
            "product_image_url": self.product_image_url,
            "product_price": self.product_price,
            "product_sales": self.product_sales,
            "product_asin": self.product_asin
        }
        return json.dumps(json_object, indent=2)

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.__str__()


class ProcessedProductDetails:
    def __init__(self):
        self.upserted = []
        self.up_to_date = []
        self.below_threshold = []
