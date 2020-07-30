# TARGETS
lint: ## Run linter
	tox -e lint

clean: ## Remove .tox and build dirs
	rm -rf .tox/
	rm -rf venv/
	rm -rf build/
	rm -rf out/

charms: clean
	@./scripts/build_charms.sh

pull-classic-snap:
	@wget https://github.com/omnivector-solutions/snap-slurm/releases/download/20.02/slurm_20.02.1_amd64_classic.snap

push-charms-to-edge:
	@./scripts/push_charms.sh edge

# Display target comments in 'make help'
help: 
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# SETTINGS
# Use one shell for all commands in a target recipe
.ONESHELL:
# Set default goal
.DEFAULT_GOAL := help
# Use bash shell in Make instead of sh 
SHELL := /bin/bash
