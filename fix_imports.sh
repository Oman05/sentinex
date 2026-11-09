#!/bin/bash
cd /home/oman/workshop/sentinex/frontend

sed -i 's/import { ReviewEventDetail, SIMILARITY_DISCLAIMER }/import { SIMILARITY_DISCLAIMER } from "..\/types\/review";\nimport type { ReviewEventDetail }/' src/components/AIAnalysisPanel.tsx
sed -i 's/import { ReviewAuditEntry }/import type { ReviewAuditEntry }/' src/components/AuditTimeline.tsx
sed -i 's/import { ReviewEventDetail }/import type { ReviewEventDetail }/' src/components/ComparisonViewer.tsx
sed -i 's/import { ReviewEventDetail }/import type { ReviewEventDetail }/' src/components/EvidenceViewer.tsx
sed -i 's/import { NotificationItem }/import type { NotificationItem }/' src/components/Layout.tsx
sed -i 's/import { ReviewEventSummary, SIMILARITY_DISCLAIMER }/import { SIMILARITY_DISCLAIMER } from "..\/types\/review";\nimport type { ReviewEventSummary }/' src/components/MatchCard.tsx
sed -i 's/import { ReviewDecision, EvidenceRequestType }/import type { ReviewDecision, EvidenceRequestType }/' src/components/ReviewDecisionPanel.tsx

sed -i 's/import { Clock, Activity, Star }/import { Activity, Star }/' src/components/TrackTimeline.tsx
sed -i 's/import { TrackHistory }/import type { TrackHistory }/' src/components/TrackTimeline.tsx
sed -i 's/(obs, idx)/(obs)/' src/components/TrackTimeline.tsx

sed -i 's/import React, { useEffect, useState } from .react.;/import { useEffect, useState } from "react";/' src/pages/InvestigationTasks.tsx
sed -i 's/import { ClipboardList, Search, Plus }/import { ClipboardList, Plus }/' src/pages/InvestigationTasks.tsx
sed -i 's/import { InvestigationTask }/import type { InvestigationTask }/' src/pages/InvestigationTasks.tsx
sed -i 's/listTasks(filters)/listTasks({ ...filters, assigned_to: filters.assigned_to ? parseInt(filters.assigned_to) : undefined })/' src/pages/InvestigationTasks.tsx

sed -i 's/import { ReviewEventSummary, ReviewDashboardStats, Filters }/import type { ReviewEventSummary, ReviewDashboardStats, Filters }/' src/pages/ReviewDashboard.tsx

sed -i 's/import React, { useEffect, useState } from .react.;/import { useEffect, useState } from "react";/' src/pages/ReviewDetails.tsx
sed -i 's/import { ReviewEventDetail, TrackHistory, ReviewHistory, ReviewDecision, EvidenceRequestType }/import type { ReviewEventDetail, TrackHistory, ReviewHistory, ReviewDecision, EvidenceRequestType }/' src/pages/ReviewDetails.tsx

sed -i 's/import React, { useEffect, useState } from .react.;/import { useEffect, useState } from "react";/' src/pages/ReviewHistory.tsx
sed -i 's/import { ReviewEventSummary }/import type { ReviewEventSummary }/' src/pages/ReviewHistory.tsx

sed -i '0,/import {/s/import {/import type {/' src/services/reviewApi.ts

npm run build 2>&1 | tail -30
