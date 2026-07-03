# Deployment & Submission Checklist

## Pre-Deployment Verification

- [x] API code complete and tested locally
- [x] All tests passing
- [x] Schema validation working
- [x] Catalog fully integrated
- [x] Approach document generated (2 pages)
- [x] README documentation complete
- [x] Requirements.txt with all dependencies

## Quick Verify (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run health check
python3 -c "from main import app; from fastapi.testclient import TestClient; c = TestClient(app); print(c.get('/health').json())"

# 3. Run full test suite
pytest test_main.py -v

# 4. Run demo
python3 demo.py | head -50
```

## Files for Submission

### 1. Code Files (For Deployment)
- [ ] main.py (API implementation)
- [ ] shl_catalog.json (Assessment database)
- [ ] requirements.txt (Dependencies)
- [ ] Dockerfile (Container image)
- [ ] Procfile (Deployment config)

### 2. Documentation Files (For Form)
- [ ] APPROACH_DOCUMENT.pdf (2 pages - required)
- [ ] README.md (Setup/deployment guide)
- [ ] SUBMISSION_SUMMARY.md (Compliance checklist)

### 3. Test & Verification
- [ ] test_main.py (Regression tests)
- [ ] evaluation.py (Metrics)
- [ ] demo.py (Demonstration)

## Deployment Options

### Option 1: Render (Recommended - 5 min)
1. Create Render.com account (free tier: 750 hours/month)
2. Create New → Web Service
3. Connect GitHub repo (or use public repo)
4. Set Environment Variable: GROQ_API_KEY=your_key (optional)
5. Deploy → Get public URL
6. Test: curl https://your-app.onrender.com/health

### Option 2: Railway (5 min)
1. Create Railway.app account
2. Create Project from GitHub
3. Open your service → Variables tab → New Variable
4. Add `GROQ_API_KEY=your_key` (optional; fallback works without it)
5. If you override the start command, use: `sh -c 'uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}'`
6. Deploy → Get public URL
7. Test: curl https://your-url.railway.app/health

### Option 3: Docker Local + Cloud
1. Build: docker build -t shl-recommender .
2. Test: docker run -p 8000:8000 shl-recommender
3. Push to Docker Hub or Deploy to Cloud Run

### Option 4: Heroku (Classic)
1. Create Heroku app
2. git push heroku main
3. Set config: heroku config:set GROQ_API_KEY=your_key
4. Check logs: heroku logs -t

## Deployment Verification

After deployment, verify:

```bash
# Test health endpoint
curl https://your-deployed-url/health

# Expected response:
# {"status": "ok"}

# Test chat endpoint
curl -X POST https://your-deployed-url/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Java developer assessment"}]}'

# Expected response:
# {
#   "reply": "...",
#   "recommendations": [...],
#   "end_of_conversation": false
# }
```

## Form Submission

Go to: https://shl1.fra1.qualtrics.com/jfe/form/SV_2m1srBsjt2q1r8y

Fill in:

1. **API Endpoint URL**
   - Example: https://shl-recommender-abc123.onrender.com
   - Verify /health and /chat are accessible

2. **Cold-Start Delay**
   - If using free tier: "Approximately 30-60 seconds on first request after idle period"
   - If using paid tier: "Minimal (<5 seconds)"

3. **LLM Used**
   - "Groq Mixtral-8x7b with deterministic fallback"

4. **AI Tools Used**
   - "GitHub Copilot CLI for project scaffolding; core logic written from scratch"

5. **Approach Document PDF**
   - Upload: APPROACH_DOCUMENT.pdf (2 pages)

6. **Additional Notes**
   - System uses hybrid approach: Groq LLM (fast) + keyword fallback (always works)
   - Zero hallucinations through catalog verification
   - 100% schema compliance
   - Handles all required behaviors: clarify, recommend, refine, compare

## Success Criteria

✓ Health endpoint: GET /health returns 200  
✓ Chat endpoint: POST /chat returns 200 with correct schema  
✓ All recommendations from catalog (no hallucinations)  
✓ Approach document: 2 pages, covers all requirements  
✓ Response time: <30s consistently  
✓ Works with/without Groq API key  

## Troubleshooting

**API not responding after deployment?**
- Check platform logs for errors
- Verify environment variables set correctly
- On Railway, do not use `--port $PORT` in a Docker/Image start command without `sh -c`; otherwise `$PORT` is passed literally to uvicorn
- Try local test first: python3 -c "from main import app; print('OK')"

**Timeouts?**
- Fallback logic should kick in within 5s
- Check network connectivity to Groq API (if key provided)

**Schema validation errors?**
- Review recent changes to response format
- Run: pytest test_main.py::test_chat_schema_compliance -v

**Hallucinated recommendations?**
- Should not happen - catalog verification prevents this
- If occurs: check shl_catalog.json not modified

## Timeline

- Deployment: 5-10 minutes
- Testing: 2-3 minutes
- Form submission: 2-3 minutes
- **Total**: ~15 minutes to complete

---

**Status**: Ready to deploy ✓
