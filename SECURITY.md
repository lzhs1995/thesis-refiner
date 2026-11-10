# Security and data handling

Thesis Refiner supplies workflow instructions and tools that may run with your user privileges. It is not a sandbox, a guarantee of model judgment, or automatic authorization to access applications and accounts. Use a reviewed commit or release and inspect the commands, output paths and dependencies you enable.

## Research files and writes

Keep a separate backup of original manuscripts, data, bibliographies and analysis outputs. Make named working copies before revision and inspect the resulting Word/PDF files. A tool's preview or a successful check does not guarantee that every later tool will avoid overwriting a file. Review each command's write behavior; native applications, agents and other integrated tools can modify documents or shared state.

The public installer refuses different existing maintained-file bytes, but that is a specific installation rule, not a universal no-overwrite guarantee. Preserve task-bound versions and original recovery records. Do not delete locks or replay an uncertain remote request to make a task appear complete.

## NotebookLM and external services

NotebookLM requires a Google account. Online review uploads selected manuscript sources to Google and sends prompts to the service. Before uploading, confirm that you are allowed to share the material and that the selected account and service are appropriate for it. Unpublished work, personal data, confidential research and restricted datasets may need a different handling arrangement. Do not assume that a local skill makes the online review local-only.

Local instructions and offline tests can be used without submitting a manuscript to NotebookLM. Installing Python dependencies still contacts a package index unless you supply a local package source. Other agent providers and integrated tools have their own data flows; check the actual configuration used for the task.

## Credentials and private evidence

Keep credentials, cookies, tokens, account identifiers, source documents, raw sessions, receipts, configuration backups and task packs out of public issues and example fixtures. Use synthetic or explicitly cleared examples. Review logs and screenshots before sharing; paths, source excerpts and document metadata can also contain private information.

If a credential is exposed, revoke or rotate it through the relevant service and preserve the evidence needed to investigate. Removing a secret from the latest file does not remove it from repository history or prior copies.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/lzhs1995/thesis-refiner/security/advisories/new) when the repository offers it. If that channel is unavailable, request a private contact without posting secrets, real research data or sensitive exploit details in a public issue. Include the affected commit, relevant platform, expected behavior and a minimal sanitized reproduction. Do not test against another person's account or manuscript.

There is no promised response time or automatic security update service. Check the actual release and dependency versions you use; an open development PR is not an installed fix.
