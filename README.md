# Quinone

### AI-Powered Nutrition Intelligence Platform

Quinone is a full-stack AI nutrition platform that turns meal images into structured nutrition data, health insights, and personalized recommendations.

**Image → Food & Ingredient Analysis → Nutrition Resolution → Health Scoring → Personalized Guidance**

---

## Product

Quinone goes beyond calorie tracking by combining AI vision, nutrition databases, evidence processing, health-domain scoring, personalization, and recommendation logic into a single workflow.

### Core workflow

```text
                    MEAL IMAGE
                        │
                        ▼
                AI FOOD ANALYSIS
                        │
                        ▼
             FOOD / INGREDIENT RESOLUTION
                        │
                        ▼
              USDA NUTRITION DATA
                        │
                        ▼
              NUTRIENT PROCESSING
                        │
                        ▼
             EVIDENCE & FEATURES
                        │
                        ▼
              HEALTH-DOMAIN SCORING
                        │
                        ▼
                 PERSONALIZATION
                        │
                        ▼
             RECOMMENDATION ENGINE
                        │
                        ▼
                  USER GUIDANCE
```

---

## What Quinone does

### 📸 AI Meal Analysis

Analyzes meal images and extracts structured information about foods and ingredients.

### 🧾 Food Resolution

Maps detected foods and ingredients to nutrition records using USDA FoodData Central.

### 🧬 Nutrition Intelligence

Processes macro- and micronutrient information and derives additional nutritional features.

### 🩺 Health Scoring

Evaluates nutrition-related health domains using evidence, thresholds, coefficients, interactions, and population modifiers.

### 🎯 Personalization

Uses user profile information, dietary preferences, and health-related constraints to personalize analysis and recommendations.

### 💡 Targeted Recommendations

Identifies nutritional gaps and generates food recommendations intended to address specific nutritional or health needs.

### 📊 Nutrition Insights

Provides users with a structured view of nutritional intake, health scores, contributors, and areas requiring attention.

---

## System Architecture

```text
┌───────────────────────────────┐
│        Flutter Application    │
│                               │
│  Home · Upload · Analysis     │
│  Health · Insights · Guidance │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│          FastAPI Backend      │
└───────────────┬───────────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
┌─────────────┐   ┌───────────────┐
│ AI Analysis │   │ Food Resolver │
│   Gemini    │   │     USDA      │
└──────┬──────┘   └───────┬───────┘
       │                  │
       └────────┬─────────┘
                ▼
       ┌─────────────────┐
       │ Nutrient Layer  │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Feature Engine  │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Evidence Engine │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Health Scoring  │
       └────────┬────────┘
                ▼
       ┌─────────────────────┐
       │ Personalization &   │
       │ Recommendation      │
       └─────────────────────┘
```

---

## AI & Data Pipeline

Quinone separates AI interpretation from deterministic nutrition processing.

```text
Image
  ↓
Gemini-based interpretation
  ↓
Structured food representation
  ↓
Food normalization
  ↓
USDA candidate search
  ↓
Candidate validation
  ↓
Nutrient retrieval
  ↓
Feature engineering
  ↓
Evidence evaluation
  ↓
Health-domain scoring
  ↓
Personalized recommendation
```

This separation allows AI-generated food descriptions to be validated against structured nutrition data instead of treating model output as the final source of truth.

---

## Recommendation Architecture

Recommendations are generated from multiple inputs rather than from a static list of generic "healthy foods".

```text
User Profile
     +
Current Nutrition
     +
Nutrient Targets
     +
Health Scores
     +
Dietary Preferences
     +
Health Constraints
          │
          ▼
   Candidate Generation
          │
          ▼
      Filtering
          │
          ▼
      Validation
          │
          ▼
       Ranking
          │
          ▼
 Quantity / Target Calculation
          │
          ▼
 Personalized Recommendation
```

The recommendation layer is separated from nutrition analysis so that recommendations can evolve without changing the underlying food-analysis pipeline.

---

## Health Intelligence

The backend separates several stages of health analysis:

```text
Nutrition Data
      ↓
Feature Engineering
      ↓
Evidence Evaluation
      ↓
Health Domain Aggregation
      ↓
Score + Confidence + Coverage
      ↓
Top Contributors
```

The evidence layer can incorporate:

* nutrient thresholds
* coefficients
* interactions
* confidence
* mechanisms
* pathways
* population modifiers

This allows health scoring logic to remain separate from raw nutrient retrieval.

---

## Key Engineering Decisions

### AI is not treated as the final data source

AI is used for interpreting unstructured inputs such as meal images.

Structured nutrition information is subsequently resolved and validated against nutrition data sources.

### Analysis and recommendations are separate

The system first determines what the meal contains and what its nutritional properties are.

Recommendation logic operates on those results rather than directly on the original image.

### Modular backend

Major responsibilities are separated into modules for:

* API handling
* AI analysis
* food resolution
* nutrient processing
* feature engineering
* evidence evaluation
* health scoring
* personalization
* recommendations

### Temporary image processing

Uploaded images are processed using temporary storage rather than being treated as permanent backend files.

### Secrets remain outside the application

External API credentials are supplied through environment variables rather than embedded in application code.

---

## Repository Structure

```text
quinone/
│
├── backend/
│   ├── server.py
│   ├── analysis_engine.py
│   ├── food_resolver.py
│   ├── nutrient_profile.py
│   ├── feature_engineering.py
│   ├── evidence_engine.py
│   ├── health_domain_scoring.py
│   ├── personalization_engine.py
│   ├── recommendation_engine.py
│   └── ...
│
├── lib/
│   ├── core/
│   ├── features/
│   └── main.dart
│
├── .github/
│   └── workflows/
│
├── pubspec.yaml
├── README.md
└── ...
```

---

## Technology Stack

| Layer           | Technology            |
| --------------- | --------------------- |
| Mobile          | Flutter / Dart        |
| Backend         | Python / FastAPI      |
| AI              | Gemini                |
| Nutrition Data  | USDA FoodData Central |
| Computer Vision | AI vision analysis    |
| API             | REST                  |
| Deployment      | Render                |
| CI/CD           | GitHub Actions        |

---

## Engineering Challenges

### Unstructured food descriptions

Food detected from images does not always correspond directly to a nutrition database record.

Quinone therefore introduces a resolution layer between AI analysis and nutrient retrieval.

### Nutrition data reliability

Candidate food records require validation before their nutrition information is used downstream.

### Multi-stage health analysis

Raw nutrient quantities are not directly equivalent to health scores. Quinone therefore separates nutrient processing, feature engineering, evidence evaluation, and domain-level scoring.

### Personalized recommendations

A recommendation must account for more than nutrient deficiency. Dietary preferences, user profile information, health constraints, current intake, and target nutrients can influence candidate selection.

---

## Development Approach

Quinone was developed as an iterative AI-assisted product rather than as a single model or API experiment.

The development process follows:

```text
Problem
  ↓
Requirements
  ↓
Architecture
  ↓
Module Design
  ↓
AI-Assisted Implementation
  ↓
Testing
  ↓
Failure Investigation
  ↓
Root-Cause Analysis
  ↓
Fix
  ↓
Regression Testing
  ↓
Iteration
```

AI is used as a development accelerator, while system architecture, interfaces, validation rules, and product behavior remain explicitly defined.

---

## Local Development

### Backend

```bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env`:

```env
GEMINI_API_KEY=your_key
USDA_API_KEY=your_key
```

Run:

```bash
uvicorn server:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### Flutter

From the repository root:

```bash
flutter pub get
flutter run
```

Configure the backend base URL according to the environment being used.

---

## Project Status

Quinone is an actively developed MVP.

The core product architecture includes:

* AI meal analysis
* Food and ingredient resolution
* USDA nutrition enrichment
* Nutrient processing
* Feature engineering
* Evidence evaluation
* Health-domain scoring
* Personalization
* Recommendation workflows
* Flutter mobile interface
* Backend API
* Deployment configuration
* CI workflow

The system continues to evolve through testing, edge-case handling, recommendation refinement, and UX iteration.

---

## Future Direction

Planned areas include:

* broader food coverage
* improved food-resolution confidence
* stronger recommendation ranking
* expanded health domains
* improved validation and observability
* richer longitudinal nutrition insights
* production-scale infrastructure

---

## Author

**Bisal Debnath**

AI / Full-Stack Product Builder

[GitHub](https://github.com/debnathbisal108)
