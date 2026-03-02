import pandas as pd
import json, os, sys, re
from datetime import datetime

def parse_coordinates(coord_str):
    try:
        coord_json = json.loads(coord_str.replace('""', '"'))
        return f"{{'lat': {coord_json['latitude']}, 'lng': {coord_json['longitude']}}}"
    except:
        return ''

def to_iso_ms_z(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', ''))
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    except:
        return dt_str

def safe_get(value):
    if pd.isna(value):
        return ''
    return str(value).replace('\n', ' ').replace('\r', ' ').strip()

def extract_city_from_address(address):
    if not address:
        return ''

    postal_match = re.search(r'\b(09\d{3})\b', address)
    if postal_match:
        postal_code = postal_match.group(1)
        if '09001' <= postal_code <= '09008':
            return "Burgos"
        else:
            cp_part2 = address[postal_match.end():].strip()
            if ',' in cp_part2:
                city = cp_part2.split(',')[0].strip()
            else:
                city = cp_part2.strip()
            return city

    if ',' in address:
        before_comma = address.split(',')[0]
        return before_comma.strip().split()[-1]

    return ''

def process_reviews(reviews_file, poi_file, state):
    reviews_df = pd.read_csv(reviews_file, dtype=str)
    poi_df = pd.read_csv(poi_file, dtype=str)

    output_rows = []

    for _, review in reviews_df.iterrows():
        pid = review['place_id']
        poi = poi_df[poi_df['place_id'] == pid]
        if poi.empty:
            continue
        poi = poi.iloc[0]

        categoryName = safe_get(poi.get('main_category', ''))
        reviewsCount = safe_get(poi.get('reviews', ''))
        totalScore = safe_get(poi.get('rating', ''))
        location = parse_coordinates(safe_get(poi.get('coordinates', '')))
        address = safe_get(poi.get('address', ''))
        city = extract_city_from_address(address)

        stars = safe_get(review.get('rating', ''))
        raw_text = safe_get(review.get('review_text', ''))
        title = safe_get(review.get('place_name', ''))
        raw_date = safe_get(review.get('published_at_date', ''))
        publishedAtDate = to_iso_ms_z(raw_date)
        url = safe_get(review.get('review_link', ''))
        name = safe_get(review.get('name', ''))
        placeId = pid

        text = raw_text if raw_text else ''
        originalLanguage = 'es' if text == raw_text else ''

        output_rows.append({
            'categoryName': categoryName,
            'city': city,
            'reviewsCount': reviewsCount,
            'totalScore': totalScore,
            'stars': stars,
            'state': state,
            'text': text,
            'title': title,
            'location': location,
            'originalLanguage': originalLanguage,
            'publishedAtDate': publishedAtDate,
            'placeId': placeId,
            'url': url,
            'name': name
        })

    if not os.path.exists('outputs'):
        os.makedirs('outputs')

    output_file = os.path.join('outputs', 'processedReviews.csv')
    out_df = pd.DataFrame(output_rows)
    out_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"{output_file} generado (sobrescrito).")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python process_reviews.py <reviews_file> <poi_file> <state>")
        sys.exit(1)

    reviews_file = sys.argv[1]
    poi_file = sys.argv[2]
    state = sys.argv[3]

    process_reviews(reviews_file, poi_file, state)
