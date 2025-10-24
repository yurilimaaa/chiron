from openai import OpenAI
import os
import pandas as pd
from dotenv import load_dotenv
import requests

# Load environment variables from .env
load_dotenv()

client = OpenAI()


def load_listings(filepath='data/title-descriptions.csv'):
    df = pd.read_csv(filepath)
    df['Listing ID'] = df['Listing ID'].astype(str)
    return df.set_index('Listing ID').to_dict('index')


def fetch_listing_data(listing_id):
    url = f"https://www.getmyboat.com/api/v4/search/v1/boats/{listing_id}/?strip_tags=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        boat_id = data.get("id") or data.get("boat_id") or listing_id
        data["availability_dates"] = fetch_availability_dates(boat_id)
        data["calculated_price"] = fetch_price(boat_id)
        data["reviews"] = fetch_reviews(boat_id)
        print("📝 Reviews:", data["reviews"])
        return data
    return None


def fetch_reviews(listing_id, limit=10):
    url = f"https://www.getmyboat.com/api/v4/boats/{listing_id}/reviews/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            reviews = data.get("boat_reviews", [])
            # Extract up to 20 meaningful review texts from public_review or private_note
            review_texts = []
            for review in reviews:
                text = (review.get("public_review") or review.get("private_note") or "").strip()
                if text:
                    review_texts.append(text)
                if len(review_texts) >= 20:
                    break
            return sorted([
                {
                    "rating": r.get("rating"),
                    "date_created": r.get("date_created"),
                    "listing_accuracy": r.get("listing_accuracy"),
                    "departure_and_return": r.get("departure_and_return"),
                    "vessel_and_equipment": r.get("vessel_and_equipment"),
                    "communication": r.get("communication"),
                    "value": r.get("value"),
                    "itinerary_and_experience": r.get("itinerary_and_experience"),
                    "private_note": r.get("private_note", "").strip(),
                    "public_review": r.get("public_review", "").strip(),
                }
                for r in reviews if (r.get("public_review") or r.get("private_note"))
            ], key=lambda x: x["date_created"], reverse=True)[:10]
        else:
            print(f"⚠️ Failed to fetch reviews, status code: {response.status_code}")
            return []
    except Exception as e:
        print("❌ Exception during fetch_reviews:", e)
        return []


def generate_version1(listing_data, reviews=None):
    reviews = reviews or listing_data.get("reviews", [])
    title = listing_data.get("title") or "Boat Rental"
    description = listing_data.get("description", "")
   # print("📦 Listing Data:", {
    #    "Title": title,
    #    "Location": listing_data.get("location", {}).get("name", ""),
    #    "Capacity": listing_data.get("capacity"),
    #    "Price": listing_data.get("price_display"),
    #    "Calculated Price": listing_data.get("calculated_price", ""),
    #    "Rate Details": listing_data.get("rate", {}).get("display_price", ""),
    #    "Duration": listing_data.get("duration"),
    #    "Departure Anytime": listing_data.get("departure_anytime"),
    #    "Charter Type": listing_data.get("charter_type", ""),
    #    "Trip Types": [t.get("name") for t in listing_data.get("trip_types", [])],
    #    "Languages": [l.get("name") for l in listing_data.get("languages_spoken", [])],
    #    "Cancellation": listing_data.get("cancellation_policy", {}).get("name", ""),
    #    "Captain": listing_data.get("captain", {}).get("name"),
    #    "Amenities": [a['name'] for a in listing_data.get("amenities", [])],
    #    "Highlights": [h for h in listing_data.get("highlights", []) if h],
    #})
    location = listing_data.get("location", {}).get("name") or "Unknown Location"
    capacity = listing_data.get("capacity") or "N/A"
    price = listing_data.get("price_display") or "N/A"
    calculated_price = listing_data.get("calculated_price") or "N/A"
    rate_details = listing_data.get("rate", {}).get("display_price") or "N/A"
    duration = listing_data.get("duration") or "N/A"
    departure_anytime = listing_data.get("departure_anytime") or False
    amenities = [a.get("name", "") for a in listing_data.get("amenities", []) if a.get("name")]

    charter_type = listing_data.get("charter_type") or "N/A"
    trip_types = [t.get("name", "") for t in listing_data.get("trip_types", []) if t.get("name")]
    languages = [l.get("name", "") for l in listing_data.get("languages_spoken", []) if l.get("name")]
    cancellation = listing_data.get("cancellation_policy", {}).get("name") or "N/A"
    highlights = [h for h in listing_data.get("highlights", []) if h]
    captain = listing_data.get("captain", {}).get("name") or "N/A"

    details = f"Rate: {rate_details}\nDuration: {duration} hours\nAnytime Departure: {'Yes' if departure_anytime else 'No'}"
    details += f"\nEstimated Price (4h/2 guests): {calculated_price}"

    reviews_text = (
        "\n".join([
            f"- {(r.get('public_review') or r.get('private_note')).strip()} (⭐️ {r['rating']}, {r['date_created'][:10]})"
            for r in reviews if (r.get("public_review") or r.get("private_note"))
        ])
        if reviews else "No reviews found."
    )

    prompt = f"""
Create a renter-facing summary and 4 experience-focused tags for the following boat rental listing.

Tone of voice: Write in a tone that is confident, authentic, and optimistic. Focus on helping people plan unforgettable celebrations. Be straightforward, friendly, and human — not robotic or overly clever.

Summary: Write a 300–600 character paragraph that highlights what makes this listing easy, fun, and special. Mention any great amenities or unique features. Use warm, renter-first language that emphasizes experience, affordability, and flexibility.

Tags: Provide 4 tags renters would associate with this experience. Focus on things like occasions, vibe, group size, or boat style.

Respond with:
Summary: <summary>
Tags: <tag1>, <tag2>, <tag3>, <tag4>
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    #print("🔍 Prompt for Version 1:\n", prompt)
    #print("📨 Response:\n", response)
    content = response.choices[0].message.content
    summary = content.split("Summary:")[1].split("Tags:")[0].strip()
    tags = content.split("Tags:")[1].strip().split(',')

    return {
        "summary": summary,
        "tags": [tag.strip() for tag in tags],
        "reviews": reviews
    }


def generate_version2(listing_data, reviews=None):
    reviews = reviews or listing_data.get("reviews", [])
    title = listing_data.get("title") or "Boat Rental"
    description = listing_data.get("description", "")
    #print("📦 Listing Data:", {
    #    "Title": title,
    #    "Location": listing_data.get("location", {}).get("name", ""),
    #    "Capacity": listing_data.get("capacity"),
    #    "Price": listing_data.get("price_display"),
    #    "Calculated Price": listing_data.get("calculated_price", ""),
    #    "Rate Details": listing_data.get("rate", {}).get("display_price", ""),
    #    "Duration": listing_data.get("duration"),
    #    "Departure Anytime": listing_data.get("departure_anytime"),
    #    "Charter Type": listing_data.get("charter_type", ""),
    #    "Trip Types": [t.get("name") for t in listing_data.get("trip_types", [])],
    #    "Languages": [l.get("name") for l in listing_data.get("languages_spoken", [])],
    #    "Cancellation": listing_data.get("cancellation_policy", {}).get("name", ""),
    #    "Captain": listing_data.get("captain", {}).get("name"),
    #    "Amenities": [a['name'] for a in listing_data.get("amenities", [])],
    #    "Highlights": [h for h in listing_data.get("highlights", []) if h],
    #})
    location = listing_data.get("location", {}).get("name") or "Unknown Location"
    capacity = listing_data.get("capacity") or "N/A"
    price = listing_data.get("price_display") or "N/A"
    calculated_price = listing_data.get("calculated_price") or "N/A"
    rate_details = listing_data.get("rate", {}).get("display_price") or "N/A"
    duration = listing_data.get("duration") or "N/A"
    departure_anytime = listing_data.get("departure_anytime") or False
    amenities = [a.get("name", "") for a in listing_data.get("amenities", []) if a.get("name")]

    charter_type = listing_data.get("charter_type") or "N/A"
    trip_types = [t.get("name", "") for t in listing_data.get("trip_types", []) if t.get("name")]
    languages = [l.get("name", "") for l in listing_data.get("languages_spoken", []) if l.get("name")]
    cancellation = listing_data.get("cancellation_policy", {}).get("name") or "N/A"
    highlights = [h for h in listing_data.get("highlights", []) if h]
    captain = listing_data.get("captain", {}).get("name") or "N/A"

    details = f"Rate: {rate_details}\nDuration: {duration} hours\nAnytime Departure: {'Yes' if departure_anytime else 'No'}"
    details += f"\nEstimated Price (4h/2 guests): {calculated_price}"

    reviews_text = (
        "\n".join([
            f"- {(r.get('public_review') or r.get('private_note')).strip()} (⭐️ {r['rating']}, {r['date_created'][:10]})"
            for r in reviews if (r.get("public_review") or r.get("private_note"))
        ])
        if reviews else "No reviews found."
    )

    prompt = f"""
Turn the following boat rental listing into 3 renter-friendly highlights and 4 tags. 
The information must not be too generic, we need make sure that the actual data that is available is what is used for creating the bullets and tags
Use Getmyboat’s tone of voice: confident, friendly, authentic, and helpful. Focus on ease, celebration, and making the renter’s job easier.

- Bullet 1 (Trip Experience): Write a 120–240 character summary of what renters can expect — the vibe, destination, group energy, and how this listing helps make an occasion special.
- Bullet 2 (Boat Specific): Write a 120–240 character summary of what the boat offers — amenities, comfort, flexibility, and standout features.
- Bullet 3 (Captain/Owner): Write a 120–240 character summary of the captain or owner — their vibe, support, communication, or reviews. If the captain’s name is not available, do not invent one — simply refer to "the captain" or "the owner".

Tags “Renters say this listing is great for”: 4 simple occasion- or vibe-focused tag that show why the listing is a great experience.

Respond with:
Bullets:
- <bullet1>
- <bullet2>
- <bullet3>

Tags:  <tag1>, <tag2>, <tag3>, <tag4>
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    #print("🔍 Prompt for Version 2:\n", prompt)
    #print("📨 Response:\n", response)
    content = response.choices[0].message.content
    bullets_raw = content.split("Bullets:")[1].split("Tags:")[0].strip()
    tags_raw = content.split("Tags:")[1].strip()

    bullets = [line.strip('- ').strip() for line in bullets_raw.split('\n') if line]
    tags = [tag.strip() for tag in tags_raw.split(',')]

    return {
        "bullets": bullets,
        "tags": tags,
        "reviews": reviews
    }


# Fetch availability dates for a boat
def fetch_availability_dates(boat_id, start_date="2025-09-24", end_date="2025-12-31"):
    url = f"https://www.getmyboat.com/api/v4/instabook/availability_dates_only/"
    params = {
        "boat_id": boat_id,
        "start_date": start_date,
        "end_date": end_date
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return []

# Fetch calculated price for a boat
def fetch_price(boat_id, currency="USD", duration="PT4H", guests=2, captain_option=1):
    url = f"https://www.getmyboat.com/api/v4/boats/{boat_id}/calculate_price/"
    params = {
        "currency": currency,
        "duration": duration,
        "guests": guests,
        "captain_option": captain_option
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("display_price", "N/A")
    return "N/A"

def generate_summary_versions(listing_data, reviews):
    version1 = generate_version1(listing_data, reviews)
    version2 = generate_version2(listing_data, reviews)
    #print("🔎 Description Preview:", listing_data.get("description", "")[:100])
    #print("🗣 Review Sample:", reviews[0]['public_review'] if reviews else "No reviews found")
    return listing_data.get("headline", ""), version1, version2, listing_data.get("description", ""), reviews