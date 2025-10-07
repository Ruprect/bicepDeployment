# Bottomline Order Template Connection Fixes Summary

## Issue Identified
The deployment was failing due to incorrect Business Central connection patterns not matching the existing template standards.

## Root Cause Analysis
After examining how other Bicep files use Business Central connections, I found:

1. **Existing Pattern**: All BC calls use `ApiConnection` type with specific v3 path format
2. **Connection Reference**: Uses `@parameters('$connections')['dynamicssmbsaas']['connectionId']`
3. **Path Format**: Uses `/v3/bcenvironments/...` structure instead of direct API URLs
4. **Parameter Declaration**: Requires `$connections` parameter in workflow definition

## Fixes Applied

### 1. Added Missing Parameter Declaration
```bicep
parameters: {
  '$connections': {
    defaultValue: {}
    type: 'Object'
  }
}
```

### 2. Updated Business Central GET Operations
**Before (incorrect):**
```bicep
type: 'Http'
uri: 'https://api.businesscentral.dynamics.com/v2.0/...'
authentication: { ... }
```

**After (correct):**
```bicep
type: 'ApiConnection'
path: '/v3/bcenvironments/@{encodeURIComponent(encodeURIComponent('ENV'))}/companies/@{encodeURIComponent(encodeURIComponent('COMPANY'))}/datasets/@{encodeURIComponent(encodeURIComponent('API'))}/tables/@{encodeURIComponent(encodeURIComponent('salesOrders'))}/items'
host: {
  connection: {
    name: '@parameters(\'$connections\')[\'dynamicssmbsaas\'][\'connectionId\']'
  }
}
```

### 3. Updated Business Central PATCH Operations
Similar pattern for update operations:
- Changed from `Http` to `ApiConnection`
- Updated path to use v3 BC connector format
- Added specific item ID in path: `/items/@{encodeURIComponent(...)}`

### 4. Consistent Connection Usage
- **Connection Name**: `dynamicssmbsaas` (matches existing templates)
- **Method**: Lowercase (`get`, `patch`)
- **Path Structure**: Follows existing BC v3 connector pattern
- **Queries**: Separated into `queries` object for filters

## Final Validation Results
✅ **Template validates successfully**
- Provisioning State: Succeeded
- No errors in template validation
- Consistent with existing BC connection patterns

## Files Updated
- `02.1-BottomlineOrder.bicep` - Fixed with proper BC connection patterns

## Key Learnings
1. Always examine existing working templates for connection patterns
2. Business Central connector uses v3 API format in Logic Apps
3. `ApiConnection` type is required for managed connectors
4. Connection parameters must be declared in workflow definition
5. URL encoding is handled by the connector, not manual string building

## Next Steps
The template is now ready for successful deployment and follows the established patterns used throughout the codebase.