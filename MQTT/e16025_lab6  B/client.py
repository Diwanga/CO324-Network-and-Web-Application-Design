## This is mqtt client wchich can interact with Task APi
## for processs another pub/sub module in not required
## you can instantiate this programe as many time with differten client names for seeing realtime multi client 
## interacting with Task API. 

import json
import time
import logging
import paho.mqtt.client as mqtt
logging.basicConfig(level=logging.DEBUG)

count = 1 # to indicate part of the Task ID
tasks ={} #  to store Tasks locally

client_name =input("Enter Your(Client) Name  =  ") #get client name from user
# WE SUGGEST C1, C2, C3 .... because it want to execute DELETE and EDITE
#because TaskID is>> {clientname}_{count} <<: n increment for each client.locacaly for own task additions.
# client_name = "C2" 



def on_disconnect(client, userdata, flags, rc=0):
    m="DisConnected flags"+"result code "+str(rc)+"client1_id  "+str(client)
    # print(m)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
   # Subscribing in on_connect() means that if we lose the connection and
  # reconnect then subscriptions will be renewed.
    client.subscribe("diwanga/add")
    client.subscribe("diwanga/delete")
    client.subscribe("diwanga/edite")
    m="Connected flags"+str(flags)+"result code "+str(rc)+"client1_id  "+str(client)
    # print(m)


# The callback for when a PUBLISH message is received from the server.(for default)
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))

# The callback for when a PUBLISH message for add is received from the server
# for diwanga/add topic
def on_add(client, userdata, msg):
    global count  # inrementing local id whenever inrementing in task. 
    count=count+1    #by doing this we can see position(entry count) of the added task by seeing Task id ( {client_name}_{id} )            
    message=str(msg.payload.decode("utf-8"))
    task = json.loads(message)
    tasks[task["id"]] = task
    print(f"ADDED Task : {task}")

# The callback for when a PUBLISH message for delete is received from the server
# for diwanga/delete topic
def on_delete(client, userdata, id):
    print("come to ondelte")
    todelid=str(id.payload.decode("utf-8"))
    toid = json.loads(todelid)
    deleteid = toid["del_this_id"]
    if deleteid in tasks.keys():
      tmp = tasks.pop(deleteid)      
      deleted = json.dumps({"id": deleteid , "status": tmp['status'], "des": tmp['des']})
      print("Deleted : " + deleted)

# The callback for when a PUBLISH message for edite is received from the server
# for diwanga/edite topic
def on_edite(client, userdata, editreq):
    editerequest=str(editreq.payload.decode("utf-8"))
    erq = json.loads(editerequest)
    toediteid = erq["editeid"]
    nextstate = erq["nextstatus"]
    tasks[toediteid]["status"]= nextstate
    print(f"edited {tasks[toediteid]}")



# functions which call from clients

def add_task(description) :    
    d = {}
    global count
    d['id' ] =f'{client_name}_{count}'
    d['status' ] ='OPEN'
    d['des' ] =f'{description}' 
    task = json.dumps(d)
    topic = f"diwanga/add"
    infot = client.publish(topic, task , qos=2)
    infot.wait_for_publish()     


def del_task(id):
    if id in tasks.keys(): #minimizing mqtt traffic by pre validation 
      print("sdfsdfsdf"+id)
      delid = json.dumps({"del_this_id": f"{id}"})
      print("sending delete request")
      topic = f"diwanga/delete"
      temp = client.publish(topic, delid, qos=2) 
      temp.wait_for_publish()

def list_task():   #to know task ids for DELETE and EDITE and validation  you can use this function.
    print(f"{tasks}")  


def edite_task(id ,status):
    
    if id in tasks.keys():  #minimizing mqtt traffic by pre validation 
        task = tasks[id]
        nowstatus = task["status"]
        if  status_ok(nowstatus,status):  
             editrq = json.dumps({'editeid': f'{id}', 'nextstatus': f'{status}'})
             print("sending edite request")
             topic = f"diwanga/edite"
             temp = client.publish(topic, editrq, qos=2) #qos level 2 use as requested and more relaiable
             temp.wait_for_publish()
        else:
            print("\n INVALID STATUS.\n")  
    else:
      print("\n ID YOU ENTERD IS NOT PRESENT.\n")


#for validating next status logic
def status_ok(current: str, next: str):
    if(current=="OPEN") and (next=="ASSIGNED"):
        return True
    elif(current=="OPEN") and (next=="CANCELLED"):
    	return True
    elif(current=="ASSIGNED") and (next=="PROGRESSING"):
        return True
    elif(current=="PROGRESSING") and (next=="CANCELLED"):
        return True
    elif(current=="PROGRESSING") and (next=="DONE"):
        return True
    else:
        return False

#initiating connection with broker. and initializing functions
client = mqtt.Client(client_name)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.message_callback_add("diwanga/add", on_add)  #redirect on_message() trafic to relavant function
client.message_callback_add("diwanga/delete", on_delete)
client.message_callback_add("diwanga/edite", on_edite)

client.connect("mqtt.eclipse.org", 1883, 60)
client.loop_start()



##command line programme for interatiing with Task API.
## In here we can instantiate more than one client using multiple of this copy of pragrames and
## we can see haw all these clients syncronizing with each other. 
#this is all in one pub/sub client.

# PRESS ENTER WHENEVER YOU WANT TO TYPE or go forward.... 

# for i in range(3):
while(True):
    op =input("\nENTER OPERATION  =  \n")
    if(op == 'ADD'):
        des =input("ENter description  = \n")
        add_task(des)
    elif(op == "DELETE"):
          delid =input("\nEnter Task Id( {clientname}_{count} ) for DELETION  = \n")
          del_task(delid)
    elif(op == "EDITE"):
        editeid =input("\nEnter Task id( {clientname}_{count} ) for EDITE  = ")
        editestate =input("\nEnter state for EDITE  = \n")
        edite_task(editeid,editestate)
    elif(op == "LIST"):
        list_task()
    else:
        print("INVALID OPERATION !!! \n")
        print("AVAILABLE OPERATIONS : ADD | DELETE | LIST | EDITE")       
    time.sleep(2)

    


