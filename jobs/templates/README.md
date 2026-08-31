# Job Templates

Copy a template, fill in the inputs, drop it in `jobs/queue/`.

The worker picks it up, runs allowed tools, writes execution and artifacts, and moves it to `jobs/done/` or `jobs/blocked/`.

Do not edit templates while a job is running — copy first, then fill.
