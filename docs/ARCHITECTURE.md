# Quinone — Architecture

## 1. High-Level Architecture

```text
Flutter Client
      │
      ▼
FastAPI Backend
      │
      ├── AI Analysis
      │
      ├── Food Resolution
      │
      ├── Nutrient Processing
      │
      ├── Feature Engineering
      │
      ├── Evidence Engine
      │
      ├── Health Scoring
      │
      ├── Personalization
      │
      └── Recommendation Engine
```

## 2. Client Layer

The Flutter application provides:

* onboarding
* user profile
* meal upload
* meal analysis
* nutrition information
* health scores
* insights
* personalized guidance
* recommendation workflows

## 3. API Layer

The FastAPI backend acts as the application boundary between the mobile client and external services.

Responsibilities include:

* request validation
* image handling
* analysis orchestration
* API responses
* temporary upload management
* back-label analysis flow

## 4. AI Analysis Layer

The AI layer interprets unstructured meal and nutrition-label images and produces structured information that can be processed by downstream modules.

## 5. Food Resolution Layer

The food resolver converts AI-generated food descriptions into structured food records.

Candidate records are retrieved from USDA FoodData Central and validated before use.

## 6. Nutrition Layer

Nutrition modules retrieve and normalize nutrient information and calculate derived features.

## 7. Evidence Layer

The evidence engine applies nutrition/health rules, thresholds, coefficients, interactions, confidence and other supporting information.

## 8. Health Scoring Layer

Health-domain scoring aggregates evidence into domain-level outputs such as scores, confidence, coverage, reliability and contributors.

## 9. Recommendation Layer

The recommendation system uses:

* current nutrition
* nutrient targets
* user profile
* dietary preferences
* health constraints
* health-domain results

to generate targeted recommendations.

## 10. External Dependencies

```text
Gemini
   │
   ▼
AI meal interpretation

USDA FoodData Central
   │
   ▼
Food and nutrient resolution

Render
   │
   ▼
Backend deployment
```

## 11. Design Principle

The central architectural principle is:

> Use AI for interpretation and generation, but use explicit software logic and external structured data for validation, calculation and decision-making.
