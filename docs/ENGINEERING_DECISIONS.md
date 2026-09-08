# Quinone — Engineering Decisions

## 1. Flutter for the client

Flutter provides a single codebase for the mobile product while allowing the application UI to remain highly interactive and modular.

## 2. FastAPI for the backend

FastAPI provides a lightweight Python API layer suitable for integrating AI processing, nutrition data services, and the application's domain logic.

## 3. Separate AI interpretation from nutrition resolution

AI-generated food descriptions are not treated as authoritative nutrition records.

A dedicated resolution layer maps candidate foods to structured nutrition data.

## 4. USDA FoodData Central

A structured nutrition database provides a more consistent foundation for nutrient calculations than relying exclusively on language-model output.

## 5. Modular health analysis

Nutrition processing, feature engineering, evidence evaluation and health scoring are separated so that scoring logic can evolve independently of raw nutrition retrieval.

## 6. Separate recommendation layer

Recommendations are downstream of analysis rather than being embedded directly inside the food-analysis process.

This allows recommendation logic to evolve independently.

## 7. Environment-based secrets

External service credentials are supplied through environment variables and are not intended to be stored in source code.

## 8. Temporary image processing

Uploaded images are processed using temporary storage so that the API does not depend on a persistent local filesystem.

## 9. Structured development

The project is developed through explicit requirements, modular implementation, testing, failure investigation and iteration rather than relying on unstructured AI-generated code.
