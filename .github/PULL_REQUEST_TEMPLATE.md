## Summary

- 

## Verification

- [ ] `python -m pytest tests -q`
- [ ] `cd frontend && npm run test -- --run`
- [ ] `cd frontend && npm run build`
- [ ] Documentation updated, if behavior changed

## Operator Safety

- [ ] Observed state and configured state remain separate.
- [ ] Actions create durable `Run` records when they mutate or request mutation.
- [ ] No real IP addresses, hostnames, secrets, prompts, or local paths were added to docs/tests.
