import logging
from pprint import pformat
from typing import Sequence, Mapping, Tuple
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
import random, string, logging
import grpc, task_pb2, task_pb2_grpc


def random_string_generator(str_size) -> str: 
    return "".join(random.choice(string.ascii_letters) for x in range(str_size))


# Test that will be used to grade addTask
def test_add(stub, count) -> Mapping[int, str]:
    tasks = {}
    for i in range(count):
        desc = random_string_generator(99)
        task: task_pb2.Task = stub.addTask(wrappers_pb2.StringValue(value=desc))
        logging.debug(f"Added Task {pformat(task)}")
        tasks[task.id] = task.description

    return tasks


# Test that will be used to grade listTask
def test_list(stub, tasks: Mapping[int, str], tQuery : task_pb2.TaskQuery) -> None:
    tasklist: task_pb2.Tasks = stub.listTasks(tQuery)
    for t in tasklist.pending:
        logging.debug(f"Task {pformat(t)}")
        # Is the proper task desc is returned for this id?
        # assert t.description == tasks[t.id]


# Test that will be used to grade delTask
def test_del(stub, tasks: Mapping[int, str]) -> None:
    for id, desc in tasks.items():
        task = stub.delTask(wrappers_pb2.UInt64Value(value=id))
        logging.debug(f"Deleted Task {pformat(task)}")
        # assert desc == task.description

# Test edit task
def test_edit(stub, id: int, desc: str, state: task_pb2.TaskState):
    task = stub.editTask(task_pb2.Task(id = id ,description = desc ,state = state))
    logging.debug(f"Edited Task {pformat(task)}")




if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = task_pb2_grpc.TaskapiStub(channel)
        tasks = test_add(stub, 10)
        test_edit(stub,id=1,desc="Task 1",state= task_pb2.TaskState.ASSIGNED)
        test_edit(stub,id=2,desc="Task 2",state= task_pb2.TaskState.ASSIGNED)
        tQuery = task_pb2.TaskQuery( selected = [task_pb2.TaskState.DONE,task_pb2.TaskState.ASSIGNED] )
        test_list(stub, tasks, tQuery)
        test_del(stub, tasks)
