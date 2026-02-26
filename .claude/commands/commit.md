Create a git commit for the current changes using Conventional Commits.

Steps:
1. Run `make lint`, `make typecheck`, `make test`. If anything fails, fix it first.
2. Run `git status` and `git diff --stat` to understand what changed.
3. Stage the relevant files (not .env, data/, or other ignored files).
4. Write the commit message following Conventional Commits (https://www.conventionalcommits.org/):
   - Format: `<type>(<optional scope>): <description>`
   - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, `ci`, `perf`, `style`
   - Scope: the area of the codebase (e.g., `sources`, `api`, `frontend`, `scoring`)
   - Description: imperative mood, lowercase, no period, focused on "why" not "what"
   - Body (if needed): explain motivation and contrast with previous behavior
   - Examples:
     - `feat(api): add curated feed with score threshold`
     - `fix(sources): handle malformed RSS dates gracefully`
     - `refactor(db): extract URL normalization to shared util`
5. Commit.
