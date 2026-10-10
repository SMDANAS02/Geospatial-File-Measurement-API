# Contributing to GeoMeasure API

Thank you for your interest in contributing to GeoMeasure API! We welcome contributions from the community.

## Development Workflow

1. **Fork and Clone**
   ```bash
   git clone https://github.com/SMDANAS02/Geospatial-File-Measurement-API.git
   cd Geospatial-File-Measurement-API
   ```

2. **Backend Setup**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy .env.example .env    # On Unix: cp .env.example .env
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Running Tests**
   Ensure all backend tests pass before committing code:
   ```bash
   pytest -v
   ```

5. **Linting and Building**
   ```bash
   cd frontend
   npm run build
   ```

## Code Guidelines

- **CRS Safety**: Never calculate areas or lengths in angular degrees (e.g. EPSG:4326). Always reproject to a suitable metric projected coordinate system.
- **Archive Security**: Always validate ZIP members to prevent path traversal (Zip Slip) and enforce uncompressed extraction limits.
- **Error Responses**: Sanitize internal server paths from error responses. Never leak filesystem paths or internal tracebacks to clients.

## Pull Request Process

1. Create a feature branch (`git checkout -b feature/your-feature-name`).
2. Make clean, atomic commits with conventional commit messages.
3. Ensure the test suite passes (`pytest -v`).
4. Submit a Pull Request targeting the `main` branch with a clear description of the change.
