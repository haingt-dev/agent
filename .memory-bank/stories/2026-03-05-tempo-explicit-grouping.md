---
title: "Tempo skill dùng get-overview để đoán grouping — thay bằng hardcoded IDs"
date: 2026-03-05
tags: [skill-system, todoist, improvement]
status: micro
---

Tempo gọi `get-overview` (toàn bộ account structure) chỉ để biết task thuộc project nào. Quest và reschedule-quest đã có hardcoded IDs từ đầu. Copy IDs sang, bỏ get-overview, grouping deterministic thay vì đoán mò. 3 API calls → 2.
