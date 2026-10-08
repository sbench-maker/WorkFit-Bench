#!/bin/bash
set -u
changed_paths="$*"
eval "git diff -- $changed_paths" | sed -n '1,120p'
