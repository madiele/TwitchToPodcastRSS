#!/bin/bash

gunicorn -b :80 -w 1 --threads 5 -k gthread twitchrss:app --env SCRIPT_NAME="$SUB_FOLDER"
