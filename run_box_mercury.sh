#!/bin/bash
cd /home/domin/projects/think-box-ai
export INCEPTION_API_KEY="sk_5d211c13ca01d6c18552eeab87f5e705"
export UPSTASH_PUBLIC_BOX_URL="wanted-tuna-71803-3000.preview.box.upstash.com"
python3 experiments/box_mercury_live.py --iterations 3 --concurrency 1