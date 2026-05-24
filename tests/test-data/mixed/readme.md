# Software Engineering Best Practices

## Code Review Guidelines

### Before Submitting
- [ ] All tests pass locally
- [ ] No commented-out code
- [ ] No debug logging statements
- [ ] Documentation updated for public API changes

### During Review
- Focus on logic errors, not formatting (let the linter handle that)
- Verify edge cases are handled (null inputs, empty collections, timeouts)
- Check that error messages are actionable
- Ensure new code has corresponding tests

## Testing Strategy

### Test Pyramid
```
      /\
     /E2E\
    /------\
   /Integration\
  /------------\
 /  Unit Tests   \
/________________\
```

1. **Unit Tests**: Test individual functions in isolation. Fast, reliable, many.
2. **Integration Tests**: Test interactions between modules. Moderate speed.
3. **E2E Tests**: Test complete user workflows. Slow, brittle, few.

### Test Naming Convention
```
test_<unit>_<scenario>_<expected_behavior>
```

Examples:
- `test_user_create_with_valid_email_returns_201`
- `test_user_create_with_duplicate_email_returns_409`
- `test_search_empty_query_returns_400`

## Git Workflow

### Branch Naming
- `feature/<ticket-id>-<short-description>`
- `fix/<ticket-id>-<short-description>`
- `chore/<short-description>`

### Commit Messages
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: feat, fix, docs, style, refactor, test, chore

## Docker Best Practices

1. Use multi-stage builds to minimize image size
2. Never run as root inside containers
3. Use specific version tags, not `latest`
4. One process per container
5. Store persistent data in volumes, not container filesystem
6. Use `.dockerignore` to exclude unnecessary files
