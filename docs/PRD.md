# Quinone — Product Requirements Document

## 1. The Product

Quinone is an AI-powered nutrition intelligence platform that converts meal images and user nutrition information into structured nutrition insights, health-domain scores, and personalized recommendations.

## 2. Problem

Traditional nutrition applications primarily expose calorie and nutrient quantities.

Users still need to determine:

* What does this meal actually contain?
* Which nutrients are insufficient?
* Which health areas may require attention?
* Which foods could address those gaps?
* How should recommendations change based on the user's profile and dietary constraints?

Quinone is designed to connect these steps into a single workflow.

## 3. Core User Flow

```text
User
 ↓
Upload Meal
 ↓
AI Meal Analysis
 ↓
Food Resolution
 ↓
Nutrition Processing
 ↓
Health Analysis
 ↓
Personalization
 ↓
Recommendations
 ↓
Actionable Guidance
```

## 4. Functional Requirements

### Meal Analysis

The system must accept meal images and identify foods and ingredients.

### Nutrition Resolution

Detected foods should be mapped to structured nutrition records where possible.

### Nutrient Processing

The system should calculate nutrition values for the identified foods and meal quantities.

### Health Analysis

The system should transform nutrition information into health-domain insights.

### Personalization

The system should incorporate available user profile and dietary information.

### Recommendations

The system should generate targeted recommendations based on identified nutritional or health needs.

## 5. Non-Functional Requirements

The system should:

* keep AI and deterministic processing responsibilities separated
* validate external data before downstream use
* keep API credentials outside source code
* provide structured API responses
* support modular backend development
* remain maintainable as health domains and recommendation logic expand

## 6. Success Criteria

The product should allow a user to move from:

**meal image → structured nutrition → health insight → actionable recommendation**

without requiring the user to manually enter every food item.

## 7. Constraints

* AI output may be ambiguous.
* Food databases may contain multiple matching records.
* Nutrition values depend on food identity, preparation, and quantity.
* Health scoring requires explicit assumptions and evidence.
* External APIs may fail or change.

## 8. Current Development Priorities

1. Improve food identification and resolution.
2. Improve nutrition-data validation.
3. Improve recommendation coverage and ranking.
4. Improve health-score reliability.
5. Improve user-facing explanations.
