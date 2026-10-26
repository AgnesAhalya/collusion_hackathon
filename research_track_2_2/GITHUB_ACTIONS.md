# Run Track 2.2 in GitHub Actions

This workflow starts only when you click **Actions → Track 2.2 background experiment → Run workflow**. Each dispatch runs exactly one paid stage. Closing your browser or terminal does not stop the GitHub job.

## Set up once

In the repository's **Settings → Secrets and variables → Actions**, add these repository secrets:

- `OPENROUTER_API_KEY`: your OpenRouter API key, ideally with an account or key spending limit.
- `TRACK22_ARTIFACT_PASSPHRASE`: a random secret of at least 24 characters. Keep a copy so you can decrypt results later.

The repository is public. The workflow encrypts the saved data and raw calls before uploading the `track22-state` artifact. Never enter either secret as a workflow input or commit it to Git.

## Run the stages

Select one stage per workflow run. Use **two agents and one trial per condition**; those counts are fixed in the workflow.

| Stage | `source_run_id` | Paid calls | Local budget gate |
| --- | --- | ---: | ---: |
| `independent_control` | Leave blank | 8 game calls | $0.05 |
| `coordination_opportunity` | Run ID from control | 8 game calls | $0.05 |
| `labels` | Run ID from opportunity | 6 judge calls | $0.02 |
| `monitors` | Run ID from labels | 8 monitor calls | $0.05 |

The run ID is the number in the completed run's GitHub URL after `/actions/runs/`. The job summary also prints it. Review the result before starting the next paid stage. DeepSeek V3.2 is the default for both game agents and the game's native judge. The three label models and four monitor views remain as configured in the project. The M1-only Markdown report does not reduce the eight monitor API calls.

The game budget flag is an estimate gate, not a provider enforced hard cap. The label and monitor clients also check their local budgets. Pricing, provider routing, timeouts, and retries can change actual charges; use an OpenRouter key spending limit if your account supports one.

## Download results

Each run uploads an encrypted `track22-state` artifact, including partial saved results when a paid stage fails. GitHub retains it for 30 days. Download the artifact ZIP from the run page and unzip it. Then, from this project directory, run:

```sh
python3 scripts/unpack_github_result.py \
  /path/to/track22-state.tar.gz.enc \
  /path/to/new-output-folder
```

The script prompts privately for the artifact passphrase and creates a new folder containing `data/`, `results/`, and the stage marker. It refuses to overwrite an existing folder. Results are never committed to the public repository.
