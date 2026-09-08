# Quinone — AI Workflow

## Objective

AI is used to interpret complex unstructured inputs while deterministic software components handle validation, calculations, and downstream decisions.

## Workflow

```text
Input Image
     ↓
Gemini Vision Analysis
     ↓
Structured Food Representation
     ↓
Normalization
     ↓
USDA Candidate Search
     ↓
Candidate Validation
     ↓
Nutrient Retrieval
     ↓
Feature Engineering
     ↓
Evidence Evaluation
     ↓
Health Scoring
     ↓
Personalization
     ↓
Recommendation Generation
```

## Why this architecture?

An AI model can identify a food but may produce:

* ambiguous food names
* different preparation descriptions
* incomplete ingredient information
* inconsistent quantities
* descriptions that do not map directly to a nutrition database

Therefore AI output is treated as an intermediate representation rather than the final nutritional source of truth.

## AI Responsibilities

AI is primarily responsible for:

* interpreting images
* identifying candidate foods
* extracting structured information from labels
* handling ambiguous visual information
* assisting with natural-language interpretation

## Deterministic Responsibilities

Software components handle:

* food resolution
* database lookup
* nutrient calculations
* derived features
* validation
* health scoring
* recommendation filtering
* API contracts

## Development Philosophy

AI-assisted development is used to accelerate implementation and exploration.

The workflow remains structured:

```text
Requirement
 ↓
System design
 ↓
Context preparation
 ↓
AI-assisted implementation
 ↓
Execution
 ↓
Failure observation
 ↓
Root-cause analysis
 ↓
Targeted correction
 ↓
Regression validation
```

The objective is not to replace engineering judgment with prompting, but to use AI to increase development speed while retaining explicit system boundaries and validation.
