# Official Test Scenarios

This document defines the official test scenarios for the Distributed Task Management System. These scenarios ensure all core functionality works correctly across different use cases.

## Test Environment Requirements

### Prerequisites
- Python 3.13 with required dependencies installed
- Server running on `http://localhost:5000`
- At least one client client connected and registered
- Web browser for UI testing
- Network connectivity between server and clients

### Setup Verification
Before running any test scenario, verify:
1. Server is running and accessible
2. Client(s) are connected and show "online" status
3. WebSocket connections are established
4. Database is initialized and accessible

---

## Test Scenario: single-subtask-single-client-now

**Scenario ID**: `single-subtask-single-client-now`

**Description**: Verify that a single subtask can be created and executed immediately on one client client.

**Objective**: Test the basic task creation, distribution, and execution workflow with minimal complexity.

### Test Steps

#### 1. Environment Preparation
- [ ] Start the server: `python server/app.py`
- [ ] Start at least one client: `python client/client.py`
- [ ] Verify client shows as "online" in Client Management page
- [ ] Confirm WebSocket connection is established

#### 2. Task Creation
- [ ] Navigate to Task Management page (`http://localhost:5000/tasks`)
- [ ] Click "Create New Task" button
- [ ] Fill in task details:
  - **Task Name**: `Test Single Hostname Task`
  - **Subtasks**: Select `get_hostname` from predefined subtasks
  - **Target Clients**: Select one connected client
  - **Execution**: Set to "Execute Now" (immediate execution)
- [ ] Click "Create Task" button
- [ ] Verify task appears in task list with "pending" status

#### 3. Task Execution Monitoring
- [ ] Navigate to task details page by clicking "View Details"
- [ ] Verify task shows:
  - Status: "running" or "completed"
  - Selected client client in execution overview
  - Subtask `get_hostname` with order 0
- [ ] Monitor real-time updates via WebSocket
- [ ] Wait for task completion (should complete within 30 seconds)

#### 4. Results Verification
- [ ] Verify task status changes to "completed"
- [ ] Check subtask execution results:
  - Subtask status: "completed"
  - Result contains hostname information
  - No error messages
  - Execution time is recorded
- [ ] Verify client status returns to "idle"

#### 5. Log Verification
- [ ] Navigate to Log Management page (`http://localhost:5000/logs`)
- [ ] Verify logs show (in real-time):
  - Task creation event
  - Task distribution to client
  - Task execution start
  - Subtask completion
  - Task completion
- [ ] Confirm no error-level log entries

### Expected Results

**Task Status**: `completed`
**Subtask Status**: `completed`
**Subtask Result**: Contains valid hostname (e.g., client client name)
**Execution Time**: < 30 seconds
**Error Count**: 0
**Log Entries**: All major events logged correctly

### Success Criteria
- ✅ Task created successfully
- ✅ Task distributed to client immediately
- ✅ Subtask executed without errors
- ✅ Hostname result returned correctly
- ✅ Real-time updates work properly
- ✅ All events logged correctly
- ✅ Client returns to idle state

### Failure Conditions
- ❌ Task creation fails
- ❌ Task not distributed to client
- ❌ Subtask execution errors
- ❌ No result returned
- ❌ Timeout (> 30 seconds)
- ❌ WebSocket updates not working
- ❌ Missing or incorrect log entries

---

## Future Test Scenarios (To Be Defined)

### Planned Test Scenarios

1. **multi-subtask-single-client-now**
   - Multiple subtasks on one client, immediate execution
   
2. **single-subtask-multi-client-now**
   - Same subtask distributed to multiple clients simultaneously
   
3. **multi-subtask-multi-client-now**
   - Multiple subtasks distributed across multiple clients
   
4. **scheduled-task-execution**
   - Task scheduled for future execution
   
5. **cron-task-execution**
   - Recurring task with cron expression
   
6. **task-error-handling**
   - Task with intentional errors to test error handling
   
7. **client-disconnect-recovery**
   - Client disconnects during task execution
   
8. **server-restart-recovery**
   - Server restart with pending tasks
   
9. **concurrent-task-execution**
   - Multiple tasks running simultaneously
   
10. **large-task-dataset**
    - Tasks with large amounts of data
    
11. **custom-subtask-execution**
    - Tasks with custom command subtasks
    
12. **real-time-monitoring**
    - Verify WebSocket real-time updates work correctly

### Test Categories

- **Basic Functionality**: Core task creation and execution
- **Distributed Execution**: Multi-client scenarios
- **Scheduling**: Time-based task execution
- **Error Handling**: Failure and recovery scenarios
- **Performance**: Load and stress testing
- **Real-time Features**: WebSocket and live updates
- **Data Integrity**: Database and state consistency

---

## Test Execution Guidelines

### Manual Testing
1. Follow test steps exactly as documented
2. Record actual results vs expected results
3. Take screenshots of key UI states
4. Note any deviations or unexpected behavior
5. Document execution time and performance

### Automated Testing
- Test scenarios should be implementable as automated tests
- Use the same verification criteria
- Include setup and teardown procedures
- Generate test reports with pass/fail status

### Test Data Management
- Use consistent test data across scenarios
- Clean up test tasks after execution
- Reset database state between test runs
- Document any persistent test data

### Reporting
- Document test execution date/time
- Record software versions and environment details
- Include logs and screenshots for failures
- Provide clear pass/fail status for each scenario

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-07-02 | Initial version with single-subtask-single-client-now scenario | System |

---

*This document should be updated whenever new test scenarios are added or existing scenarios are modified.*
