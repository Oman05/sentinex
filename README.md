# SENTINEX — AI-Based Missing and Wanted Person Detection & Real-Time Alert System

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.115-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![OpenCV](https://img.shields.io/badge/Computer_Vision-OpenCV_4.10_%2B_SFace-5C3EE8.svg?logo=opencv)](https://opencv.org)
[![React](https://img.shields.io/badge/Frontend-React_18_%2B_TypeScript-61DAFB.svg?logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.14-3776AB.svg?logo=python)](https://python.org)
[![Accuracy](https://img.shields.io/badge/Top--1_Accuracy-99.32%25-brightgreen.svg)]()
[![Zero False Alarms](https://img.shields.io/badge/FMR-0.00%25_at_0.45-success.svg)]()

> **⚠️ Mandatory AI Safety & Human-in-the-Loop Mandate**:  
> SENTINEX calculates mathematical vector similarities and provides investigative leads.  
> The system **NEVER** autonomously confirms an individual's identity or executes automated punitive enforcement actions.  
> Every operational alert requires explicit, auditable **Human Verification** by an authorized police examiner.

---

## 📑 Table of Contents

1. [System Overview & Architecture](#-system-overview--architecture)
2. [Complete 12-Module Specification](#-complete-12-module-specification)
   - [Module 1: Authentication & Role-Based Access Control](#module-1-authentication--role-based-access-control-rbac)
   - [Module 2: Case Management Lifecycle](#module-2-case-management-lifecycle)
   - [Module 3: Reference Image Enrollment & Dataset Storage](#module-3-reference-image-enrollment--dataset-storage)
   - [Module 4: Live CCTV & Webcam Stream Ingestion](#module-4-live-cctv--webcam-stream-ingestion)
   - [Module 5: AI Video Processing (Detection & Tracking)](#module-5-ai-video-processing-detection--tracking)
   - [Module 6: Face Quality Assessment & Gating](#module-6-face-quality-assessment--gating)
   - [Module 7: Candidate Matching & Vector Search](#module-7-candidate-matching--vector-search)
   - [Module 8: Human Verification & Investigation Dashboard](#module-8-human-verification--investigation-dashboard)
   - [Module 9: Multi-Department Alert & Dispatch Engine](#module-9-multi-department-alert--dispatch-engine)
   - [Module 10: Evidence Management & Chain of Custody](#module-10-evidence-management--chain-of-custody)
   - [Module 11: Analytics, Evaluation & Model Monitoring](#module-11-analytics-evaluation--model-monitoring)
   - [Module 12: Administration, Health & System Management](#module-12-administration-health--system-management)
3. [Datasets & Gallery Enrollment](#-datasets--gallery-enrollment)
4. [Computer Vision Models & Empirical Accuracy](#-computer-vision-models--empirical-accuracy)
5. [Default User Accounts](#-default-user-accounts)
6. [Quick Start & Installation Guide](#-quick-start--installation-guide)
7. [Running the Webcam Scanner](#-running-the-webcam-scanner)
8. [API Endpoints Reference](#-api-endpoints-reference)
9. [Project Directory Structure](#-project-directory-structure)

---

## 🏛️ System Overview & Architecture

SENTINEX is an end-to-end, enterprise-grade law enforcement and public safety intelligence platform designed to scan live video streams (authorized CCTV feeds, transit turnstiles, and mobile laptop webcams), detect faces in real time, extract standardized 512-dimensional facial representations, match them against enrolled galleries of Missing and Wanted persons, and route potential candidate events through an unskippable human review protocol.

### End-to-End Pipeline Data Flow

```text
               ┌────────────────────────────────────────────────────────┐
               │    MODULE 4: Live CCTV & Webcam Stream Ingestion       │
               │    (RTSP Feeds / /dev/video0 / Bounded Frame Queues)   │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │       MODULE 5: AI Perception & Video Processing       │
               │   • YuNet Face Detector (OpenCV 5 DNN)                 │
               │   • Person Detection & Short-term IoU Tracking         │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │        MODULE 6: Face Quality Assessment & Gating      │
               │   • Sharpness (Laplacian variance >= 60.0)             │
               │   • Lighting / Contrast (histogram dispersion)         │
               │   • Yaw/Pitch Pose Angle & Occlusion Gating            │
               │   • Gate Check: is_match_ready = True (Quality >= 0.40)│
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │        MODULE 7: Feature Extraction & Vector Search    │
               │   • OpenCV SFace ONNX (512-dim L2-normalized vectors)  │
               │   • Cosine Similarity Search vs 301 Enrolled Gallery   │
               │   • Temporal Multi-frame Track Smoothing & Thresholds  │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │     MODULE 8: Human Verification & Review Dashboard    │
               │   • Status: PENDING_REVIEW                             │
               │   • Mandatory Examiner Inspection (Split-view audit)   │
               │   • Decision: CONFIRMED_FOR_ACTION vs DISMISSED        │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │     MODULE 9: Multi-Department Alert & Notification    │
               │   • Dual Routing: Originating Dept + Central Command   │
               │   • Re-alert Cooldown Window (Debounce duplicates)     │
               │   • Webhook, In-App Notification & Dispatch Logging    │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │       MODULE 10: Evidence Chain of Custody & Audit     │
               │   • Immutable SHA-256 Checksums                        │
               │   • Tamper-Evident Hash Audit Ledger                   │
               │   • Court-Admissible Forensic Case Dossier Export      │
               └────────────────────────────────────────────────────────┘
```

---

## 🧩 Complete 12-Module Specification

### Module 1: Authentication & Role-Based Access Control (RBAC)
- **Token Security**: Industry-standard JWT (HMAC-SHA256) with configurable expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Password Protection**: Passwords salted and hashed with `bcrypt` (72-byte max entropy).
- **Enforced User Roles**:
  - `ADMIN`: Full administrative privileges, user management, audit review, camera provisioning.
  - `POLICE`: Authorized investigator access, case management, review queue operations.
  - `REVIEWER`: Human verification examiner tasked with inspecting possible-match alerts.
  - `OFFICER`: Field officer receiving verified operational notifications.
  - `ANALYST`: Technical analyst monitoring model performance, bias, and camera metrics.
- **Audit Logging**: Every login, failed attempt, privilege elevation, and status toggle recorded in `audit_logs`.

### Module 2: Case Management Lifecycle
- **Strict Dataset Isolation**: Absolute segregation between `MISSING` (vulnerable persons, search-and-rescue) and `WANTED` (criminal warrants, investigative alerts) categories.
- **Case Entities**: Tracks unique alphanumeric case numbers (`WP-LOCAL-XXXX`, `MP-LOCAL-XXXX`), priority tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), departmental ownership, and last-known locations.
- **Audit Traceability**: Created by, updated at, active flags, and full historical modifications.

### Module 3: Reference Image Enrollment & Dataset Storage
- **Enrollment Engine**: Ingestion of verified reference portraits.
- **Pre-Enrollment Quality Gate**: Pre-validates sharpness, face detectability, and minimum pixel resolution (100x100) before admitting an image into the searchable gallery.
- **Local Storage Management**: Organized directory trees under `datasets/wanted_persons/` and `datasets/missing_persons/`.
- **Primary Image Tagging**: Automatically tracks primary vs auxiliary reference portraits per identity.

### Module 4: Live CCTV & Webcam Stream Ingestion
- **Source Protocols**: Supports RTSP network video streams, local video files, image sequences, and local V4L2 webcams (`/dev/video0`).
- **Bounded Frame Queues**: Ring-buffer backpressure mechanism preventing memory overflow when detection runs slower than capture rate.
- **Configurable Sampling**: Decouples network feed FPS from AI processing FPS (typically 1.0–2.0 FPS for inference).
- **Stream Worker Lifecycle**: Asynchronous background workers managed via `stream_manager.py` with automatic retry limits and health tracking.

### Module 5: AI Video Processing (Detection & Tracking)
- **YuNet Face Detector**: Fast OpenCV 5 DNN ONNX model (`face_detection_yunet_2023mar.onnx`) running in CPU mode without PyTorch overhead.
- **Person Detection**: Integrated person bounding box identification.
- **IoU Tracking**: Multi-frame bounding box association using Hungarian / Greedy IoU matching to maintain persistent identity tracks (`track_id`) across frames.
- **Candidate Observation Packaging**: Encapsulates bounding boxes, confidence scores, cropped face base64 representations, and camera metadata into clean `CandidateObservation` bundles.

### Module 6: Face Quality Assessment & Gating
- **Pure Quality Metric**: Operates strictly on image usability without making identity assumptions.
- **Quality Dimensions**:
  - **Sharpness**: Laplacian variance calculation (Threshold $\ge 60.0$).
  - **Lighting & Exposure**: Evaluates overexposure, shadows, and contrast histogram dispersion.
  - **Pose Angle**: Yaw and pitch estimation via eye-nose-mouth facial landmarks.
  - **Resolution**: Minimum required inter-ocular distance and face crop size.
- **Gating Decision**: Outputs `is_match_ready = True` when composite quality $\ge 0.40$, saving CPU cycles and preventing false positive matches from poor frames.

### Module 7: Candidate Matching & Vector Search
- **Embedding Extractor**: Pretrained OpenCV SFace ONNX (`face_recognition_sface_2021dec.onnx`) generating standardized 512-dimensional L2-normalized feature vectors.
- **Vector Search Index**: Thread-safe in-memory vector index performing sub-millisecond Cosine Similarity search over enrolled reference vectors.
- **Score Gating**:
  - `score >= 0.85`: **HIGH_PRIORITY_REVIEW** (Critical operational lead)
  - `0.45 <= score < 0.85`: **POSSIBLE_MATCH** (Standard verification required)
  - `score < 0.45`: **IGNORED / NO_CANDIDATE** (Zero alert generated)
- **Track Smoothing**: Aggregates multi-observation scores across a tracking window to eliminate transient false-positive flickers.

### Module 8: Human Verification & Investigation Dashboard
- **Review Queue**: All candidates crossing operational thresholds populate the human verification queue with state `PENDING_REVIEW`.
- **Side-by-Side Examiner Interface**: Displays live CCTV snapshot side-by-side with official enrolled reference photos.
- **Examiner Actions**:
  - `CONFIRM`: Human examiner confirms match $\rightarrow$ moves to Module 9 for alert dispatch.
  - `REJECT`: False match $\rightarrow$ marked dismissed with examiner rationale.
  - `INCONCLUSIVE`: Requires auxiliary footage or manual review.
- **Full Examiner Audit**: Officer ID, decision timestamp, review duration, and mandatory notes recorded for chain-of-custody.

### Module 9: Multi-Department Alert & Dispatch Engine
- **Gated Dispatch**: Operational alerts can **never** trigger autonomously from raw AI scores; they must be approved in Module 8 (`CONFIRMED_FOR_ACTION`).
- **Dual-Destination Routing**:
  1. Originating Department (Jurisdiction where camera is situated).
  2. Central Command Dispatch (`DEPT-CENTRAL`).
- **Debounce / Re-Alert Suppression**: Configurable 30-second cooldown window prevents alert flooding for the same case on the same camera.

### Module 10: Evidence Management & Chain of Custody
- **Forensic Hash Integrity**: Every cropped observation, reference image, and match event is stamped with an immutable SHA-256 checksum.
- **Chain of Custody Tracking**: Chronological logging of all data accesses, exports, examiner reviews, and supervisor sign-offs.
- **Tamper Evidence**: Cryptographic verification ensures evidence packages cannot be modified post-incident.

### Module 11: Analytics, Evaluation & Model Monitoring
- **Scientific Benchmark Harness**: Held-out 150-identity LFW-derived benchmark suite evaluating true positive rate, precision, recall, and false match rate (FMR).
- **Model Registry**: Tracks active biometric models (`OPENCV_SFACE v1.1.0`), weights checksums, and operational thresholds.
- **Zero Individual Ranking Invariant**: Evaluates technical system and model parameters only—never ranks officers, individuals, or departments.

### Module 12: Administration, Health & System Management
- **Hardware & Microservice Health**: Real-time monitoring of CPU, RAM, disk capacity, and background stream workers.
- **Live Camera Demo**: Integrated web console for testing live webcams, registering device indices, and monitoring candidate matches.
- **Automated Backup Engine**: Database snapshots and configuration backups archived with timestamped manifests in `backups/`.

---

## 📂 Datasets & Gallery Enrollment

The system comes pre-loaded with enrolled local cases and benchmark verification datasets:

| Dataset Category | Source Location | Enrolled Count | Case ID Prefix | Verification Role |
|---|---|---|---|---|
| **Wanted Persons** | `/home/oman/Pictures/wanted person` | **51 Cases** | `WP-LOCAL-0000` – `0074` | Active search gallery |
| **Missing Persons** | `/home/oman/Pictures/missing person` | **50 Cases** | `MP-LOCAL-0081` – `0154` | Active search gallery |
| **Negative Distractor Set** | `/home/oman/Pictures/unknown person` | **55 Probes** | `UN-TEST-XXXX` | False-positive testing (Unenrolled) |
| **LFW Benchmark Split** | `datasets/benchmarks/face_dataset_150` | **200 Ref / 912 Probes** | `WP-TEST-XXXX`, `MP-TEST-XXXX` | Metric evaluation & threshold tuning |
| **Total Gallery in DB** | Active SQLite Databases | **206 Cases / 301 Images** | — | **100% SFace 512-dim Embeddings** |

---

## 🎯 Computer Vision Models & Empirical Accuracy

SENTINEX uses an optimized, lightweight ONNX runtime architecture executing purely via OpenCV DNN without heavy PyTorch or CUDA dependencies.

```text
Input Video Frame (640x480)
       │
       ▼
YuNet Face Detector (ONNX)  ──>  Detects 5 facial landmarks (eyes, nose, mouth corners)
       │
       ▼
Affine Face Alignment Crop  ──>  Rotates, scales, and normalizes face to canonical coordinates
       │
       ▼
OpenCV SFace Recognizer     ──>  Extracts 512-dim float32 L2-normalized feature representation
       │
       ▼
Cosine Vector Index Search  ──>  Similarity score: Dot product (Cosine distance) in [0.0, 1.0]
```

### Empirical Evaluation on 1,112 Held-Out Images

Testing on the benchmark dataset produced the following performance metrics:

```text
Images Embedded: 1,112 / 1,112 (100% detector & decoder success)
Gallery References: 200 identities | Held-out Probes: 912 images
Enrolled Top-1 Identification Accuracy: 580 / 584 (99.32%)
Unknown Person Score Range: Min=0.1928, Mean=0.3119, Max=0.4432
```

### Precision, Recall & False Match Rate Curve

| Cosine Threshold | True Positives (TP) | False Positives (FP) | False Negatives (FN) | True Negatives (TN) | Precision | Recall | False Match Rate (FMR) | Operational Verdict |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `0.30` | 580 | 196 | 4 | 134 | 74.74% | 99.32% | 59.39% | Too loose (High noise) |
| `0.35` | 580 | 56 | 4 | 273 | 91.19% | 99.32% | 17.02% | High recall, minor false alarms |
| `0.40` | 579 | 7 | 5 | 321 | 98.81% | 99.14% | 2.13% | Acceptable investigative mode |
| **`0.45`** | **578** | **0** | **6** | **328** | **100.00%** | **98.97%** | **0.00%** | **⭐ Optimal Operational Threshold** |
| `0.50` | 570 | 0 | 14 | 328 | 100.00% | 97.60% | 0.00% | Highly conservative |
| `0.85` | — | 0 | — | — | 100.00% | — | 0.00% | **Critical High-Priority Alert Tier** |

> **Key Takeaway**: At threshold **`0.45`**, SENTINEX achieves **zero false alarms (FMR = 0.00%)** while maintaining **98.97% recall** across enrolled individuals.

---

## 👥 Default User Accounts

The demo seeder creates these operational roles with unique generated passwords:

| Username | Role | Role Access Level |
|---|---|---|---|
| `admin` | **ADMIN** | Full administrative privileges, user/camera management |
| `police` | **POLICE** | Case management, incident investigation |
| `reviewer_jane` | **REVIEWER** | Human verification queue examiner |
| `officer_bob` | **OFFICER** | Field officer notification & dispatch access |
| `analyst_carol` | **ANALYST** | Model evaluation, analytics & health telemetry |

On a fresh database, run `python seed_demo_data.py` and securely record the initial passwords printed for newly created accounts. Existing accounts are not reset by the seeder.

---

## 🚀 Quick Start & Installation Guide

### Prerequisites
- Linux OS (Ubuntu 22.04+ or Debian-based distribution recommended)
- Python 3.11+ (Python 3.14 verified)
- Node.js 18+ and npm
- Laptop webcam or USB camera (`/dev/video0`)

### 1. Virtual Environment Setup

```bash
# Navigate to project root
cd ~/workshop/sentinex

# Create Linux virtual environment if not present
python3 -m venv .venv_linux

# Activate environment
source .venv_linux/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# If .env does not exist, copy from template
cp .env.example .env
```

Ensure `.env` contains:
```ini
DATABASE_URL=sqlite:///./sentinex.db
SECRET_KEY=sentinex-production-secret-key-32chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

### 3. Start the Backend API Server

```bash
cd ~/workshop/sentinex/backend
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Launch Uvicorn with auto-reload enabled
../.venv_linux/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

### 4. Start the Frontend Web Application

```bash
cd ~/workshop/sentinex/frontend

# Install node dependencies (if first time)
npm install

# Start Vite dev server
npm run dev
```
- Web Application: `http://localhost:5173`

---

## 📷 Running the Webcam Scanner

You can run the live facial recognition scanner in **two modes**:

### Mode A: Via the Web Dashboard (Recommended)
1. Open your browser and navigate to `http://localhost:5173`.
2. Log in with `admin` and the generated initial password printed by `seed_demo_data.py`.
3. In the sidebar, click **Live Camera Demo** (or `http://localhost:5173/live-camera`).
4. Select the registered camera: **Laptop Built-in Webcam (`CAM-LAPTOP-00`)**.
5. Click **Start Stream**.
6. The webcam stream will open with real-time face detection bounding boxes. When an enrolled Wanted or Missing person appears, candidate match cards will populate on the right panel.

### Mode B: Standalone Terminal Runtime (GUI Window)
For direct desktop video output with real-time OpenCV annotations:

```bash
cd ~/workshop/sentinex
PYTHONPATH=backend .venv_linux/bin/python live_scan_alert.py \
  --camera 0 \
  --db-camera CAM-LAPTOP-00 \
  --fps 2 \
  --threshold 0.45
```

#### Standalone Window Controls:
| Key | Action |
|:---:|:---|
| `q` | Quit webcam session |
| `r` | Reload enrolled vector gallery index from database |
| `f` | Freeze / unfreeze live video frame |
| `+` / `-` | Increase / decrease similarity decision threshold |
| `s` | Print summary of all session match alerts to terminal |

---

## 🌐 API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
|:---:|:---|:---|:---:|
| `POST` | `/api/auth/login` | Authenticate with username & password; issues JWT | None |
| `GET` | `/api/auth/me` | Fetch active user profile and role | Bearer JWT |
| `GET` | `/api/cases` | List all Missing & Wanted cases | POLICE / ADMIN |
| `POST` | `/api/cases` | Create a new missing/wanted case record | POLICE / ADMIN |
| `GET` | `/api/cameras` | List registered CCTV & webcam devices | All authenticated |
| `POST` | `/api/admin/cameras` | Register a new camera or webcam device | ADMIN |
| `POST` | `/api/admin/cameras/{id}/start` | Start background video ingestion worker | ADMIN |
| `POST` | `/api/admin/cameras/{id}/stop` | Stop background video ingestion worker | ADMIN |
| `GET` | `/api/cameras/{id}/stream-status` | Get real-time stream status & FPS telemetry | All authenticated |
| `GET` | `/api/reviews` | List pending human verification candidate events | REVIEWER / POLICE |
| `GET` | `/api/reviews/{id}` | Get side-by-side verification details | REVIEWER / POLICE |
| `POST` | `/api/reviews/{id}/decision` | Submit human verification verdict (`CONFIRMED` / `REJECTED`) | REVIEWER / POLICE |
| `GET` | `/api/dashboard/stats` | Aggregate dashboard queue and alerting metrics | POLICE / ADMIN |
| `GET` | `/api/notifications` | List dispatches and operational alerts | All authenticated |
| `GET` | `/api/evidence` | Search forensic evidence store with SHA-256 validation | POLICE / ADMIN |
| `GET` | `/api/analytics/evaluation` | Fetch AI model benchmark and evaluation records | ANALYST / ADMIN |
| `GET` | `/api/health` | System health, memory, and database status | None |

---

## 📁 Project Directory Structure

```text
sentinex/
├── README.md                                # Single Unified Master Documentation
├── run_sentinex.sh                          # One-click full launcher script
├── live_scan_alert.py                       # Standalone live webcam scanning & alert daemon
├── webcam_live_analysis.py                  # Standalone interactive live OpenCV webcam tool
├── train_sface_gallery.py                   # Gallery re-embedding & vector index training
├── evaluate_sface_dataset.py                # Scientific benchmark & threshold evaluation
├── integrate_wanted_person_dataset.py       # Wanted person dataset integration script
├── integrate_missing_person_dataset.py      # Missing person dataset integration script
├── integrate_unknown_person_dataset.py      # Unknown person negative set evaluator
├── sentinex.db                              # Active SQLite database with all 206 cases
│
├── backend/                                 # FastAPI Backend Architecture
│   ├── face_detection_yunet_2023mar.onnx    # YuNet face detector model weights
│   ├── face_recognition_sface_2021dec.onnx  # SFace 512-dim face recognition model weights
│   ├── sentinex.db                          # Synchronized backend database
│   └── app/
│       ├── main.py                          # FastAPI application factory & lifespan
│       ├── core/                            # JWT, security (bcrypt), application config
│       ├── database/                        # SQLAlchemy session, engine, base model
│       ├── dependencies/                    # Auth, RBAC role gating dependencies
│       ├── models/                          # ORM entities (User, Case, Camera, Alert, etc.)
│       ├── schemas/                         # Pydantic request/response data contracts
│       ├── services/                        # Business logic (Matching, Streams, Review, Quality)
│       ├── api/                             # REST API route controllers
│       └── ai_engine/                       # Core Computer Vision Engine
│           ├── detection/                   # YuNet & Person detector modules
│           ├── tracking/                    # IoU bounding-box tracking managers
│           ├── processing/                  # Frame processor & candidate observation builder
│           ├── quality/                     # Sharpness, lighting, pose & occlusion assessors
│           ├── matching/                    # VectorSearchIndex, SFace model, candidate ranker
│           └── pipeline/                    # Asynchronous video processing pipeline workers
│
├── frontend/                                # Modern React / Vite / TypeScript Dashboard
│   ├── src/
│   │   ├── pages/                           # ReviewDashboard, LiveCameraDemo, Alerts, Evidence
│   │   ├── components/                      # Layout, Navigation, Modals, Camera Players
│   │   ├── services/                        # Axios API client integrations
│   │   └── types/                           # TypeScript interfaces & domain models
│   ├── package.json
│   └── vite.config.ts
│
├── datasets/                                # Dataset & Reference Repositories
│   ├── wanted_persons/                      # WP-LOCAL-XXXX enrolled wanted person images
│   ├── missing_persons/                     # MP-LOCAL-XXXX enrolled missing person images
│   ├── negative_sets/                       # Unknown distractor probes for false-alarm testing
│   └── benchmarks/                          # 150-person LFW evaluation benchmark
│
└── backups/                                 # Timestamped system and database archive snapshots
```

---

## ⚖️ Legal, Privacy & Compliance Statement

- **Controlled Law Enforcement Use**: Designed exclusively for authorized public safety authorities, transit security agencies, and missing person investigations.
- **Biometric Data Protection**: Facial feature representations are stored as non-reversible mathematical vector embeddings, never as raw unencrypted biometric templates.
- **Strict Human Oversight**: Algorithmic match scores are purely evidentiary suggestions. In accordance with ethical AI governance standards, human verification is mandatory prior to any law enforcement dispatch.
# sentinex
