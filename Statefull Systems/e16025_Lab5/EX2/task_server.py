"""TODO:
    * Implement error handling in TaskapiImpl methods
    * Implement saveTasks, loadTasks
    * Implement TaskapiImpl.editTask (ignoring write conflicts)
    * Fix data race in TaskapiImpl.addTask
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
from pprint import pformat
from typing import Mapping, Sequence, Tuple

from google.protobuf import (
    any_pb2,
    api_pb2,
    duration_pb2,
    empty_pb2,
    field_mask_pb2,
    source_context_pb2,
    struct_pb2,
    timestamp_pb2,
    type_pb2,
    wrappers_pb2,
)

import task_pb2, task_pb2_grpc
import grpc
from grpc import server
import threading

# define max length of the task
MAX_LENGTH = 1024

class TaskapiImpl:
    def __init__(self, taskfile: str):
        self.taskfile = taskfile
        self.task_id = 0
        self.lock = threading.Lock()
        self.initStates()

    def __enter__(self):
        """Load tasks from self.taskfile"""
        with open(self.taskfile, mode="rb") as t:
            tasklist = task_pb2.Tasks()
            tasklist.ParseFromString(t.read())
            logging.info(f"Loaded data from {self.taskfile}")
            self.tasks: Mapping[int, task_pb2.Task] = {}
            # add to the dict and set id with maximum value
            for t in tasklist.pending:
                self.tasks[t.id] = t
                if self.task_id < t.id :
                    self.task_id = t.id
            self.task_id +=1
            print(f"next task id = {self.task_id}")
            
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Save tasks to self.taskfile"""
        with open(self.taskfile, mode="wb") as t:
            tasks = task_pb2.Tasks(pending=self.tasks.values())
            t.write(tasks.SerializeToString())
            logging.info(f"Saved data to {self.taskfile}")


    def addTask(self, request: wrappers_pb2.StringValue, context) -> task_pb2.Task:
        logging.debug(f"addTask parameters {pformat(request)}")
        # check if the lenght of the task description is acceptable.
        if len(request.value) >= 1024 :
            # if not handle it
            context.set_code(grpc.StatusCode.OUT_OF_RANGE)
            context.set_details(f'Task descriptions must be less than {MAX_LENGTH} characters.!')
            return task_pb2.Task()
        else :
            # if task description is acceptable add the task
            # lock the critical region
            self.lock.acquire()
            t = task_pb2.Task(id=self.task_id, description=request.value, state=task_pb2.TaskState.OPEN)
            # increment task_id
            self.task_id += 1
            # release the lock.
            self.lock.release()
            # add to the dict
            self.tasks[t.id] = t
            # return task
            return t

    def delTask(self, request: wrappers_pb2.UInt64Value, context) -> task_pb2.Task:
        logging.debug(f"delTask parameters {pformat(request)}")
        # check task id is a valid value.
        if request.value not in self.tasks.keys() :
            # if not handle it
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Invalid task id.!')
            return task_pb2.Task()
        else :
            # remove the task and send the deleted task
            return self.tasks.pop(request.value)

    def listTasks(self, request: task_pb2.TaskQuery, context) -> task_pb2.Tasks:
        logging.debug(f"listTasks parameters {pformat(request)}")
        tasks = [ task for task in self.tasks.values() if task.state in request.selected or len(request.selected) == 0 ]
        print(tasks)
        return task_pb2.Tasks(pending=tasks)

    def editTask(self, request: task_pb2.Task, context) -> task_pb2.Task:
        logging.debug(f"edit task parameters {pformat(request)}")
        # first validate the inputs recieved from the client.
        if request.id not in self.tasks.keys() :
            # if not handle it
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Invalid task id')
            return task_pb2.Task()
        elif len(request.description) >= 1024 :
            # if not handle it
            context.set_code(grpc.StatusCode.OUT_OF_RANGE)
            context.set_details(f'Task descriptions must be less than {MAX_LENGTH} characters.!')
            return task_pb2.Task()
        elif request.state not in self.nextStates(self.tasks[request.id].state):
            # handle illegal state transitions.
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(self.getErrorMsg(self.tasks[request.id].state))
            return task_pb2.Task() 
        else :
            # update task
            self.tasks[request.id] = task_pb2.Task(id = request.id ,description = request.description, state=request.state)
            # return updated task
            return self.tasks[request.id]

    def initStates(self):
        # initialize states and its next possible states.
        self.states = {}
        self.states[task_pb2.TaskState.OPEN] = [task_pb2.TaskState.ASSIGNED,task_pb2.TaskState.CANCELLED,task_pb2.TaskState.OPEN]
        self.states[task_pb2.TaskState.ASSIGNED] = [task_pb2.TaskState.ASSIGNED,task_pb2.TaskState.PROGRESSING]
        self.states[task_pb2.TaskState.PROGRESSING] = [task_pb2.TaskState.DONE,task_pb2.TaskState.CANCELLED,task_pb2.TaskState.PROGRESSING]
        self.states[task_pb2.TaskState.DONE] = [task_pb2.TaskState.DONE]
        self.states[task_pb2.TaskState.CANCELLED] = [task_pb2.TaskState.CANCELLED]
        # initialize the error messages.
        self.stateErrors = {}
        self.stateErrors[task_pb2.TaskState.OPEN] = "Opened task must assign or cancel."
        self.stateErrors[task_pb2.TaskState.ASSIGNED] = "Assigned task must go progressing"
        self.stateErrors[task_pb2.TaskState.PROGRESSING] = "Progressing taskmust cancel or done."
        self.stateErrors[task_pb2.TaskState.DONE] = "Task state done."
        self.stateErrors[task_pb2.TaskState.CANCELLED] = "Task state cancel"

    # This function will return next possible states for a given state.
    def nextStates(self, state: task_pb2.TaskState) -> [task_pb2.TaskState]:
        return self.states[state]
    
    # This function will return error msg for a given state.
    def getErrorMsg(self, state: task_pb2.TaskState) -> str:
        return self.stateErrors[state]


TASKFILE = "tasklist.protobuf"
if __name__ == "__main__":
    Path(TASKFILE).touch()
    logging.basicConfig(level=logging.DEBUG)

    with ThreadPoolExecutor(max_workers=1) as pool, TaskapiImpl(
        TASKFILE
    ) as taskapiImpl:
        taskserver = server(pool)
        task_pb2_grpc.add_TaskapiServicer_to_server(taskapiImpl, taskserver)
        taskserver.add_insecure_port("[::]:50051")
        try:
            taskserver.start()
            logging.info("Taskapi ready to serve requests")
            taskserver.wait_for_termination()
        except:
            logging.info("Shutting down server")
            taskserver.stop(None)
