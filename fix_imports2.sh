#!/bin/bash
cd /home/oman/workshop/sentinex/frontend

sed -i 's/AlertCircle, //g' src/components/AIAnalysisPanel.tsx
sed -i 's/User, //g' src/components/AuditTimeline.tsx
sed -i 's/import React, { useEffect, useState } from .react.;/import { useEffect, useState } from "react";/' src/components/Layout.tsx
sed -i 's/const \[notifications, setNotifications\] = useState<NotificationItem\[\]>(\[\]);/const [, setNotifications] = useState<NotificationItem[]>([]);/' src/components/Layout.tsx

npm run build 2>&1 | tail -30
