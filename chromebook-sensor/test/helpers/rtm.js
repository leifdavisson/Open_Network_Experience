/**
 * Test Annotation Helper for AST Requirements Traceability Matrix (RTM)
 * License: GNU AGPLv3
 */

export function verifies(reqId, testTitle) {
  return (testFn) => {
    return async (...args) => {
      return await testFn(...args);
    };
  };
}
