"""TODO:
    * Implement error handling in TaskapiImpl methods
    * Implement saveTasks, loadTasks
    * Implement TaskapiImpl.editTask (ignoring write conflicts)
    * Fix data race in TaskapiImpl.addTask
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from pprint import pformat
from typing import Mapping, List

import grpc
from google.protobuf import (
    empty_pb2,
    wrappers_pb2,
)
from grpc import server

import task_pb2
import task_pb2_grpc



class TaskapiImpl:
    def __init__(self, taskfile: str):
        self.taskfile = taskfile
        self.task_id = 0
        self.mutex = threading.Lock()

    def __enter__(self):
        """Load tasks from self.taskfile"""
        with open(self.taskfile, mode="rb") as t:
            tasklist = task_pb2.Tasks()
            tasklist.ParseFromString(t.read())
            logging.info(f"Loaded data from {self.taskfile}")
            self.tasks: Mapping[int, task_pb2.Task] = {}
            taskid_temp: int
            for item in tasklist.pending:
                self.tasks[item.id] = item             
                taskid_temp = item.id
            self.task_id = taskid_temp + 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Save tasks to self.taskfile"""
        with open(self.taskfile, mode="wb") as t:
            tasks = task_pb2.Tasks(pending=self.tasks.values())
            t.write(tasks.SerializeToString())
            logging.info(f"Saved data to {self.taskfile}")

    def addTask(self, request: wrappers_pb2.StringValue, context) -> task_pb2.Task:
        if len(request.value) <= 1024:
            with self.mutex:
                logging.debug(f"addTask parameters {pformat(request)}")
                t = task_pb2.Task(id=self.task_id, description=request.value)
                self.tasks[self.task_id] = t
                self.task_id += 1
                return t
        else:
            context.set_code(grpc.StatusCode.STRINGEXCEED)
            context.set_details('Description is too long!')
            return None

    def delTask(self, request: wrappers_pb2.UInt64Value, context) -> task_pb2.Task:
        if request.value in self.tasks:
            logging.debug(f"delTask parameters {pformat(request)}")
            return self.tasks.pop(request.value)
        else:
            context.set_code(grpc.StatusCode.INVALIDID)
            context.set_details('Invalid Id!')
            return None

    # Implementing TaskapiImpl.editTask (ignoring write conflicts)
    
    def editTask(self, request: task_pb2.Task, context) -> task_pb2.Task:
        if request.id in self.tasks and len(request.description) <= 1024:
            temp = self.tasks[request.id]
            self.tasks[request.id] = request.description
            return task_pb2.Task(id=request.id, description=temp)
        else:
            context.set_code(grpc.StatusCode.STRINGEXCEEDORINVALIDID)
            context.set_details('Description is too long or Invalid Id!')
            return None

    def listTasks(self, request: empty_pb2.Empty, context) -> task_pb2.Tasks:
        logging.debug(f"listTasks parameters {pformat(request)}")
        return task_pb2.Tasks(pending=self.tasks.values())


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