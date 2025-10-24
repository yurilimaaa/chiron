# stop env ctrl+C
# start env 
# FLASK_APP=listing_summary/main.py flask run

#!/usr/bin/env python3
"""Main Flask app for listing summary generator."""

# stop env ctrl+C
# start env 
# FLASK_APP=listing_summary/main.py flask run

import os
import requests
from listing_summary.llm_utils import generate_summary_versions
from flask import Flask, render_template, request

app = Flask(__name__, template_folder="templates")

@app.route("/", methods=["GET", "POST"])
def index():
    listing_data = {}
    reviews = []
    listing_id = ""

    if request.method == "POST":
        listing_id = request.form.get("listing_id", "").strip()
        if not listing_id:
            return render_template(
                "index.html",
                listing_data={},
                reviews=[],
                listing_id="",
                title="",
                version1="",
                version2="",
                error="Please enter a valid Listing ID."
            )

        # Fetch listing data
        listing_url = f"https://www.getmyboat.com/api/v4/search/v1/boats/{listing_id}/?strip_tags=true"
        try:
            response = requests.get(listing_url)
            if response.status_code == 200:
                listing_data = response.json()
            else:
                print(f"⚠️ Failed to fetch listing data, status code: {response.status_code}")
        except Exception as e:
            print("❌ Exception during listing fetch:", e)

        # Fetch reviews
        reviews = fetch_reviews(listing_id)

        # Generate LLM summaries
        title, version1, version2, description, review_list = "", "", "", "", []
        if listing_data:
            try:
                result = generate_summary_versions(listing_data, reviews)
                if isinstance(result, (list, tuple)) and len(result) == 5:
                    title, version1, version2, description, review_list = result
                else:
                    raise ValueError("generate_summary_versions returned unexpected format")
            except Exception as e:
                print("❌ Exception during LLM generation:", e)
                title, version1, version2, description, review_list = "", "", "", "", []

        return render_template(
            "index.html",
            listing_data=listing_data,
            reviews=reviews,
            listing_id=listing_id,
            title=title,
            version1=version1,
            version2=version2,
            description=description,
            review_list=review_list
        )

    return render_template(
        "index.html",
        listing_data={},
        reviews=[],
        listing_id="",
        title="",
        version1="",
        version2="",
        description="",
        review_list=[]
    )

def fetch_reviews(listing_id):
    url = f"https://www.getmyboat.com/api/v4/boats/{listing_id}/reviews/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            reviews = []
            for r in data.get("results", []):
                if isinstance(r, dict):
                    review_text = r.get("public_review") or r.get("text") or ""
                    if review_text.strip():
                        r["public_review"] = review_text.strip()
                        reviews.append(r)
            return reviews
        else:
            print(f"⚠️ Failed to fetch reviews, status code: {response.status_code}")
            return []
    except Exception as e:
        print("❌ Exception during fetch_reviews:", e)
        return []

if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )