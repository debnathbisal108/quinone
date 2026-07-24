# Nutrica Backend

Nutrica Backend is a FastAPI service used by the Nutrica mobile application. It receives meal images, extracts structured food information with Gemini, resolves foods against USDA FoodData Central, attaches nutrients, computes derived features, evaluates nutrition evidence, and calculates health-domain scores.

## Current pipeline

```text
Mobile app
    |
    v
server.py
    |
    v
analysis_engine.py
    |
    v
food_resolver.py
    |
    v
nutrient_profile.py
    |
    v
feature_engineering.py
    |
    v
evidence_engine.py
    |
    v
health_domain_scoring.py
    |
    v
JSON response
```

## Repository structure

```text
nutrica-backend/
├── server.py
├── analysis_engine.py
├── food_resolver.py
├── nutrient_profile.py
├── feature_engineering.py
├── evidence_engine.py
├── health_domain_scoring.py
├── requirements.txt
├── render.yaml
├── .python-version
├── .env.example
├── .gitignore
└── README.md
```

This API does not render web pages, so it does not need `templates/` or `static/` directories. Uploaded images are stored in request-local temporary directories and removed after processing.

## Module responsibilities

### `server.py`

Defines FastAPI endpoints, validates uploads, manages temporary files and back-label sessions, runs the analysis pipeline, and returns JSON.

### `analysis_engine.py`

Sends meal and nutrition-label images to the Gemini API and returns structured meal JSON.

### `food_resolver.py`

Resolves detected foods, ingredients, and spices to USDA FoodData Central records.

### `nutrient_profile.py`

Downloads and normalizes nutrient data for resolved FDC records.

### `feature_engineering.py`

Calculates derived nutrition features, including nutrient densities, ratios, amino-acid indicators, and other analysis inputs.

### `evidence_engine.py`

Applies scientific thresholds, coefficients, interactions, confidence values, mechanisms, pathways, and optional population modifiers.

### `health_domain_scoring.py`

Groups evidence by canonical health domain and calculates score, confidence, coverage, reliability, and top contributors.

## API endpoints

### Health check

```http
GET /health
```

Expected response:

```json
{
  "status": "healthy"
}
```

### Analyze a meal

```http
POST /analyze
```

Multipart form fields:

- `image`: required meal image
- `profile`: optional JSON string containing user-supplied profile information
- `front_label`: optional packaged-food front-label image
- `back_label`: optional nutrition-label image

The exact accepted fields depend on the current `server.py` implementation.

### Continue nutrition-label analysis

```http
POST /analyze/back-label
```

Used when the first analysis response requests a separate back-label image.

## Local setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file from `.env.example`, or configure variables in your shell:

```text
GEMINI_API_KEY=your_key
USDA_API_KEY=your_key
NUTRICA_LOG_LEVEL=INFO
```

The application code must read both API keys from environment variables. Do not hard-code credentials in Python files.

### 4. Run the API

Linux or macOS:

```bash
export GEMINI_API_KEY="your_key"
export USDA_API_KEY="your_key"
uvicorn server:app --reload
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your_key"
$env:USDA_API_KEY="your_key"
uvicorn server:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Deploy to Render

The repository includes `render.yaml`, which defines one Python web service.

1. Push the repository to GitHub.
2. Sign in to Render.
3. Select **New +** and then **Blueprint**.
4. Connect the GitHub repository.
5. Render detects `render.yaml`.
6. Enter secret values for:
   - `GEMINI_API_KEY`
   - `USDA_API_KEY`
7. Deploy the Blueprint.
8. Test:

```text
https://YOUR-SERVICE-NAME.onrender.com/health
```

Render uses:

```text
Build command:
pip install --upgrade pip && pip install -r requirements.txt

Start command:
uvicorn server:app --host 0.0.0.0 --port $PORT
```

## Mobile-app connection

Use the deployed Render base URL in Flutter:

```dart
const String apiBaseUrl =
    'https://YOUR-SERVICE-NAME.onrender.com';
```

Do not place Gemini or USDA secret keys in the Flutter application. All requests requiring those keys must pass through this backend.

## Important deployment notes

### API keys

Before uploading to GitHub, search every Python file for hard-coded keys:

```bash
grep -R "API_KEY" .
```

Move real keys to environment variables. If a real key has already been shared or committed, revoke or rotate it.

The resolver and nutrient modules should use:

```python
USDA_API_KEY = os.environ.get("USDA_API_KEY")

if not USDA_API_KEY:
    raise RuntimeError("USDA_API_KEY is not configured.")
```

### Temporary storage

Render's local filesystem is ephemeral. This project already uses temporary upload directories, which is appropriate. Do not rely on local files for permanent user data.

Optional USDA cache paths are blank by default. Configure persistent storage before enabling disk-backed cache files.

### Free service behavior

A free Render web service is suitable for development and demonstrations, but it can spin down while inactive and may have limited CPU and memory. Production traffic should use a paid instance.

## GitHub checklist

Before the first push:

- Rename `health_domain_scoring_modified.py` to `health_domain_scoring.py`.
- Use the updated `server.py`.
- Confirm all imports match the final filenames.
- Remove notebooks, combined scratch files, pasted-text files, and duplicate code unless intentionally retained.
- Remove all hard-coded Gemini and USDA keys.
- Add real secrets only in the Render dashboard.
- Test `python -m compileall .`.
- Test `uvicorn server:app --reload`.
- Test `/health`, `/analyze`, and `/analyze/back-label`.

## License

Add the appropriate license before making the repository public.
