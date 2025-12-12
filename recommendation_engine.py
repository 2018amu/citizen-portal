# recommendation_engine.py

import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


class RecommendationEngine:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.client["citizen_portal"]
        self.newusers_col = self.db["webusers"]
        self.eng_col = self.db["engagements"]
        self.ads_col = self.db["ads"]

    # -------------------------------
    # USER SEGMENTATION
    # -------------------------------
    def get_user_segment(self, user_id):
        user = self.newusers_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            return ["unknown"]

        profile = user.get('extended_profile', {})
        children = profile.get('family', {}).get('children', [])
        job = profile.get('career', {}).get('current_job', 'unknown')
        education = profile.get('education', {}).get('highest_qualification', 'unknown')

        age = profile.get('family', {}).get('age') or user.get('profile', {}).get('basic', {}).get('age')
        try:
            age_int = int(age)
        except (TypeError, ValueError):
            age_int = None

        segment = []

        # Age-based segments
        if age_int is not None:
            if age_int < 25:
                segment.append("young_adult")
            elif 25 <= age_int <= 35:
                segment.append("early_career")
            elif 36 <= age_int <= 45:
                segment.append("mid_career_family")
            elif 46 <= age_int <= 60:
                segment.append("established_professional")
            else:
                segment.append("senior")

        # Education segments
        if education in ['none', 'school', 'ol']:
            segment.append("needs_qualification")
        elif education in ['al', 'diploma']:
            segment.append("mid_education")
        elif education in ['degree', 'masters', 'phd']:
            segment.append("highly_educated")

        # Family segments
        if children:
            segment.append("parent")

        children_ages = profile.get('family', {}).get('children_ages', [])
        children_ages_int = []
        for a in children_ages:
            try:
                children_ages_int.append(int(a))
            except (TypeError, ValueError):
                continue

        if any(5 <= a <= 10 for a in children_ages_int):
            segment.append("primary_school_parent")
        if any(11 <= a <= 16 for a in children_ages_int):
            segment.append("secondary_school_parent")
        if any(17 <= a <= 20 for a in children_ages_int):
            segment.append("university_age_parent")

        # Career segments
        if job and "government" in job.lower():
            segment.append("government_employee")
        if job and any(word in job.lower() for word in ["manager", "director", "head"]):
            segment.append("management")

        return list(set(segment))

    # -------------------------------
    # PERSONALIZED AD RECOMMENDATION
    # -------------------------------
    def get_personalized_ads(self, user_id, limit=5):
        segments = self.get_user_segment(user_id)
        user_engagements = list(self.eng_col.find({"user_id": user_id}))

        # Extract interests
        interests = []
        for eng in user_engagements:
            interests.extend(eng.get('desires', []))
            if eng.get('question_clicked'):
                interests.append(eng['question_clicked'])
            if eng.get('service'):
                interests.append(eng['service'])

        # Get all active ads
        ads = list(self.ads_col.find({"active": True}))
        scored_ads = []

        for ad in ads:
            score = 0
            ad_tags = ad.get('tags', [])
            ad_segments = ad.get('target_segments', [])

            # Segment matching
            score += len(set(segments) & set(ad_segments)) * 10
            # Interest matching
            score += len(set(interests) & set(ad_tags)) * 5
            # Recency boost
            if ad.get('created'):
                days_old = (datetime.utcnow() - ad['created']).days
                if days_old < 7:
                    score += 5
                elif days_old < 30:
                    score += 2

            scored_ads.append((ad, score))

        # Sort by score
        scored_ads.sort(key=lambda x: x[1], reverse=True)
        top_ads = [ad for ad, score in scored_ads[:limit]]

        # Fallback: if no top ads, return some active ads
        if not top_ads and ads:
            top_ads = ads[:limit]

        # Fallback: if still empty, return a default ad
        if not top_ads:
            top_ads = [{
                "title": "Explore Our Services",
                "message": "Check out popular programs and courses tailored for you",
                "tags": [],
                "type": "default"
            }]

        return top_ads

    # -------------------------------
    # EDUCATION RECOMMENDATION
    # -------------------------------
    def generate_education_recommendations(self, user_id):
        user = self.newusers_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            return []

        profile = user.get('extended_profile', {})
        education = profile.get('education', {})
        career = profile.get('career', {})
        age = profile.get('family', {}).get('age')

        # Convert age to int safely
        try:
            age_int = int(age)
        except (TypeError, ValueError):
            age_int = None

        recommendations = []

        # User's own education recommendation
        if (
            education.get('highest_qualification') in ['ol', 'al', 'diploma']
            and 'government' in career.get('current_job', '').lower()
            and age_int is not None
            and 25 <= age_int <= 50
        ):
            recommendations.append({
                "type": "education",
                "title": "Complete Your Degree",
                "message": "Enhance your career with a recognized degree program",
                "priority": "high",
                "tags": ["degree", "government", "career_advancement"]
            })

        # Children education recommendations
        children_ages = profile.get('family', {}).get('children_ages', [])
        children_education = profile.get('family', {}).get('children_education', [])

        # Convert children ages safely
        children_ages_int = []
        for ch_age in children_ages:
            try:
                children_ages_int.append(int(ch_age))
            except (TypeError, ValueError):
                children_ages_int.append(None)

        for i, ch_age in enumerate(children_ages_int):
            edu_level = children_education[i] if i < len(children_education) else ""
            if ch_age is None:
                continue

            # O/L guidance for ages 10–18
            if 10 <= ch_age <= 18 and "ol" not in edu_level.lower():
                recommendations.append({
                    "type": "child_education",
                    "title": "O/L Exam Preparation",
                    "message": "Special courses for your child's O/L exams",
                    "priority": "medium",
                    "tags": ["ol_exams", "tuition", "secondary_education"]
                })

            # A/L guidance for ages 17–20
            if 17 <= ch_age <= 20 and "al" not in edu_level.lower():
                recommendations.append({
                    "type": "child_education",
                    "title": "A/L Stream Selection Guidance",
                    "message": "Expert guidance for A/L subject selection",
                    "priority": "medium",
                    "tags": ["al_exams", "career_guidance", "higher_education"]
                })

        return recommendations
