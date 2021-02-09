"""TODO:
    * Implement error handling in TaskapiImpl methods
    * Implement saveTasks, loadTasks
    * Implement TaskapiImpl.editTask (ignoring write conflicts)
    * Fix data race in TaskapiImpl.addTask
"""
import grpc

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
from pprint import pformat
from typing import Mapping, Sequence, Tuple
from threading import Lock

from dataclasses import dataclass

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
from grpc import server, StatusCode
import task_pb2, task_pb2_grpc

@dataclass
class data_str:
    date: timestamp_pb2.Timestamp
    # task: task_pb2.Task() = None
    task_des: str = None


class TaskapiImpl:
    def __init__(self, taskfile: str):
        self.taskfile = taskfile
        self.task_id = 0
        self.lck = Lock()

    def __enter__(self):
        """Load tasks from self.taskfile"""
        with open(self.taskfile, mode="rb") as t:
            tasklist = task_pb2.Tasks()
            tasklist.ParseFromString(t.read())
            logging.info(f"Loaded data from {self.taskfile}")
            self.tasks: Mapping[int, task_pb2.Task] = self.mmp(tasklist) #TODO
            
            #for keep histry
            self.hist_tasks: Mapping[int, List[data_str]] = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Save tasks to self.taskfile"""
        with open(self.taskfile, mode="wb") as t:
            tasks = task_pb2.Tasks(pending=self.tasks.values()) #TODO
            t.write(tasks.SerializeToString())
            logging.info(f"Saved data to {self.taskfile}")

# function for create dic
    def mmp(cls, tsk: task_pb2.Tasks) -> Mapping[int, task_pb2.Task]:
        inf = {}
        for t in tsk.pending:
            inf[t.id] = t
        return inf

    def addTask(self, request: wrappers_pb2.StringValue, context) -> task_pb2.Task:
        logging.debug(f"addTask parameters {pformat(request)}")
        # here handle the MAXLEN = 1024 if description too long give an error
        if len(request.value)>1024:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details('Oh!.. Description length is too big.!')
            return task_pb2.Task()

        # if description is in range
        with self.lck:
            t = task_pb2.Task(id=self.task_id, description=request.value)
            self.tasks[self.task_id] = t
            self.hist_tasks[self.task_id] = [(data_str(date=timestamp_pb2.Timestamp().GetCurrentTime()))]
            self.task_id += 1
        return t

    def delTask(self, request: wrappers_pb2.UInt64Value, context) -> task_pb2.Task:
        logging.debug(f"delTask parameters {pformat(request)}")
        # check whether the key is exist
        if request.value in self.tasks.keys():
            # remove both histry and tasks
            self.hist_tasks.pop(request.value)
            return self.tasks.pop(request.value)

        #if not
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"There is no Task with Id : {pformat(request)}")
        return task_pb2.Task()

    def listTasks(self, request: empty_pb2.Empty, context) -> task_pb2.Tasks:
        logging.debug(f"listTasks parameters {pformat(request)}")
        return task_pb2.Tasks(pending=self.tasks.values())


# this is nondestructive_editTask
# create data class with description and date
# for memory wastage i'm not goint to store updated task in both hist_tasks and tasks
    def nondestructive_editTask(self, request: task_pb2.Task, context):
        logging.debug(f"editTask parameters {pformat(request)}")
        
        # check whether the key is exist and description length
        if request.id in self.tasks.keys() and len(request.description) <= 1024:
            with self.lck:
                # add current task to histry
                self.hist_tasks[request.id][len(self.hist_tasks[request.id])-1].task_des = self.tasks[request.id].description
                # append new task histry's date
                self.hist_tasks[request.id].append(data_str(date=timestamp_pb2.Timestamp().GetCurrentTime()))
                # update with new description
                self.tasks[request.id].description = request.description
                return self.tasks[request.id]
        
        #error 
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"There is no Task with Id : {pformat(request.id)} or Description is too long")
        return task_pb2.Task()

# this is destructive_editTask 
    def destructive_editTask(self, request: task_pb2.Task, context):
        logging.debug(f"editTask parameters {pformat(request)}")
        
        # check whether the key is exist and description length
        if request.id in self.tasks.keys() and len(request.description) <= 1024:
            #delete task
            self.delTask(wrappers_pb2.UInt64Value(value=request.id), context)
            # adding agin
            return(self.addTask(wrappers_pb2.StringValue(value=request.description), context))
             
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"There is no Task with Id : {pformat(request.id)} or Description is too long")
        return task_pb2.Task()      



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
