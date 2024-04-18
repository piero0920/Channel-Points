from __future__ import annotations
import os, pathlib, requests, re, json, base64, time
from dotenv import load_dotenv
from datetime import datetime
from typing import Union

root_path = str(pathlib.Path(__file__).parent)
load_dotenv(dotenv_path=os.path.join(root_path, '.env'))


AUTH = os.getenv("AUTH_TOKEN")

GQL_URL = "https://gql.twitch.tv/gql"
GQL_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

STREAMERS = [
    {
        "streamer": str(os.getenv("STREAMER_1")).lower(),
        "points": 0,
        "SpadeUrl": ""
    },
    {
        "streamer": str(os.getenv("STREAMER_2")).lower(),
        "points": 0,
        "SpadeUrl": ""
    }
]

USER_ID = ""
TICKETCOUNT = 0

OLDPOINTS = {
    str(os.getenv("STREAMER_1")).lower(): 0,
    str(os.getenv("STREAMER_2")).lower(): 0
}

def GQL_Request(operationName: str, query: str, variables: dict, version: int, sha256Hash: str) -> Union[dict | None]: 
    gql_query = {
        "operationName": operationName,
        "query": query, 
        "variables": variables,
        "extensions": {
            "persistedQuery": {
                "version": version,
                "sha256Hash": sha256Hash
            }
        }
    }

    headers = {
        "Authorization": f'OAuth {AUTH}',
        "Client-ID": GQL_ID
    }

    response = requests.post(GQL_URL, headers=headers, json=gql_query)

    if response.status_code == 200:
        return response.json()
    else:
        return None


def channelPointsRunner():

    global USER_ID
    global TICKETCOUNT
    global OLDPOINTS

    for streamer in STREAMERS:

        variables = {
            "channelLogin": streamer["streamer"]
        }

        res = GQL_Request("ChannelPointsContext", "", variables, 1 , "9988086babc615a918a1e9a722ff41d98847acac822645209ac7379eecb27152")

        newPoints = int(res["data"]["community"]["channel"]["self"]["communityPoints"]["balance"])
        streamer["points"] = newPoints

    if AUTH != "":
        if USER_ID == "":
            
            
            res = GQL_Request("Core_Services_Spade_CurrentUser", "", {}, 1, "482be6fdcd0ff8e6a55192210e2ec6db8a67392f206021e81abe0347fc727ebe")

            USER_ID = res["data"]["currentUser"]["id"]
        
        query = """
                query {{
                    users(logins: ["{}", "{}"]) {{
                        id,
                        login,
                        displayName,
                        stream{{
                            id
                        }}
                    }}
                }}
""".format(STREAMERS[0]["streamer"], STREAMERS[1]["streamer"])


        liveRes = GQL_Request("", query, {}, 1, "")

        for i in range(len(liveRes["data"]["users"])):
            if liveRes["data"]["users"][i]["stream"] == None:
                del liveRes["data"]["users"][i]

        TICKETCOUNT += 1
        if TICKETCOUNT % 60 == 0:
            for streamer in STREAMERS:
                streamer["SpadeUrl"] = ""

        for i in range(len(liveRes["data"]["users"])):
            streamData = next((user for user in liveRes["data"]["users"] if str(user["login"]).lower() == STREAMERS[i]["streamer"]), None)
            
            variables = {
                "channelLogin": STREAMERS[i]["streamer"]
            }
            gqlRes = GQL_Request("ChannelPointsContext", "", variables, 1, "9988086babc615a918a1e9a722ff41d98847acac822645209ac7379eecb27152")

            newPoints = int(gqlRes["data"]["community"]["channel"]["self"]["communityPoints"]["balance"])
            if gqlRes["data"]["community"]["channel"]["self"]["communityPoints"]["availableClaim"] is not None:
                claim_id = gqlRes["data"]["community"]["channel"]["self"]["communityPoints"]["availableClaim"]["id"]
                variables = {
                    "input": {
                        "channelID": streamData["id"], 
                        "claimID": claim_id
                    }
                }

                GQL_Request("ClaimCommunityPoints", "", variables, 1, "46aaeebe02c99afdf4fc97c7c0cba964124bf6b0af229395f1f6d1feed05b3d0")
            
            if STREAMERS[i]["SpadeUrl"] == "":
                url = f"https://www.twitch.tv/{STREAMERS[i]['streamer']}"
                headers = {
                    "Authorization": f'OAuth {AUTH}',
                    "Client-ID": GQL_ID
                }
                response = requests.get(url, headers=headers)
                #print(response.text)
                # '(foo|bar)'
                regex = r"(https://assets.twitch.tv/config/settings.*?js|https://static.twitchcdn.net/config/settings.*?js)"                
                settings_match = re.search(regex, response.text)
                settings_url = settings_match.group(0)
                settings_response = requests.get(settings_url, headers=headers)
                spade_url = json.loads(settings_response.text[28:])["spade_url"]
                STREAMERS[i]["SpadeUrl"] = spade_url
            
            data = {
                "channel_id": streamData["id"],
                "broadcast_id": streamData["stream"]["id"],
                "player": "site",
                "user_id": USER_ID
            }

            data_root = {
                "event": "minute-watched",
                "properties": data
            }

            payload = json.dumps(data_root, separators=(',', ':')).encode('utf-8')
            payload_base64 = base64.b64encode(payload).decode('utf-8')

            requests.post(STREAMERS[i]["SpadeUrl"], data=payload_base64)
            
            if str(streamData["login"]).lower() in OLDPOINTS:
                if newPoints > OLDPOINTS[str(streamData["login"]).lower()] and OLDPOINTS[str(streamData["login"]).lower()] != 0:
                    print(datetime.now())
                    print(f'Recieved {newPoints - OLDPOINTS[str(streamData["login"]).lower()]} points from channel {STREAMERS[i]["streamer"]}.')
                    print(f'Points: {newPoints}')
                    OLDPOINTS[str(streamData["login"]).lower()] = newPoints
                else:
                    OLDPOINTS[str(streamData["login"]).lower()] = newPoints   
            else:
                OLDPOINTS[str(streamData["login"]).lower()] = newPoints   

while True:
    channelPointsRunner()

    time.sleep(60)