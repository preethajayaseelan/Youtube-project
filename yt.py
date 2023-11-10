import streamlit as st
from streamlit_option_menu import option_menu
import pymongo as py
import pandas as pd
import plotly.express as px
import mysql.connector as sql
from googleapiclient.discovery import build
from datetime import datetime


 # Set page configuration and title
st.set_page_config(page_title="YouTube Data Harvesting and Warehousing", layout="wide")
 # Set option menu
with st.sidebar:
    selected = option_menu("Main Menu", ["Home", "Explore", "View"],
                           icons=['house', "tools", 'card-text'], menu_icon="cast", default_index=1)

# Connect to databases (MongoDB, MySQL)
# MongoDB
vinoth = py.MongoClient("mongodb+srv://preethajayaseelan:!Charupree1329@cluster0.0oaukvs.mongodb.net/?retryWrites=true&w=majority")
db = vinoth["youtube_channel_data"]

# MySQL
mydb = sql.connect(host="localhost",
                  user="root",
                  password="!Charupree1329",
                  database="youtube")
cursor = mydb.cursor()

# Build a connection with the YouTube API to access channel data
# API Key
api_key = "AIzaSyAuJgAz9N7z0CMkk_PZ9rQGkyNLrhuBU1U"

# Build access service
youtube = build("youtube", "v3", developerKey=api_key)

# Function to get channel details
def channel_details(channel_id):
    channel_data = []
    request = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id)
    response = request.execute()

    for i in range(len(response["items"])):
        data = {
            "channel_id": channel_id,
            "channel_name": response["items"][i]["snippet"]["title"],
            "channel_description": response["items"][i]["snippet"]["description"],
            "subscribers": response["items"][i]["statistics"]["subscriberCount"],
            "channel_views": response["items"][i]["statistics"]["viewCount"],
            "channel_total_videos": response["items"][i]["statistics"]["videoCount"],
            "playlist_id": response["items"][i]["contentDetails"]["relatedPlaylists"]["uploads"],
            "channel_country": response["items"][i]["snippet"].get("country")
        }
        channel_data.append(data)

    return channel_data


# Function to get video IDs (used to get all video details)
# Get the upload playlist ID to get video details
def get_video_ids(channel_id):
    video_ids = []
    request = youtube.channels().list(
        part="contentDetails",
        id=channel_id)
    response = request.execute()
    playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            playlistId=playlist_id,
            part="contentDetails",
            maxResults=50,
            pageToken=next_page_token).execute()

        for i in range(len(request["items"])):
            video_ids.append(request["items"][i]["contentDetails"]["videoId"])
            next_page_token = request.get("nextPageToken")

        if next_page_token is None:
            break

    return video_ids


# Function to get video details
def get_video_details(video_ids):
    video_data = []
    for i in range(0, len(video_ids), 50):
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids[i:i+50])).execute()
        for video in request["items"]:
            video_details = {
                "channel_name": video['snippet']["channelTitle"],
                "channel_id": video["snippet"]["channelId"],
                "video_id": video["id"],
                "title": video["snippet"]["title"],
                "tags": video["snippet"].get("tags", []),
                "thumbnail": video["snippet"]["thumbnails"]["default"]["url"],
                "Description": video['snippet']['description'],
                "Published_date": video['snippet']['publishedAt'],
                "Duration": video['contentDetails']['duration'],
                "Views": video['statistics']['viewCount'],
                "Likes": video['statistics'].get('likeCount'),
                "Comments": video['statistics'].get('commentCount'),
                "Favorite_count": video['statistics']['favoriteCount'],
                "Definition": video['contentDetails']['definition'],
                "Caption_status": video['contentDetails']['caption']
            }
            video_data.append(video_details)
    return video_data


# Function to get channel name in MongoDB
def get_channel_name():
    channel_names = []
    for doc in db.channel_details.find():
        channel_names.append({"channel_name": doc["channel_name"]})
    return channel_names

channel_name = get_channel_name()


if selected == "Explore":
    tab1,tab2 = st.tabs(["EXTRACT ", "TRANSFORM "])

    with tab1:
        st.write("Enter your channel_id below")
        channel_id = st.text_input("Enter")

        if channel_id and st.button("Extract"):
            channel_data = channel_details(channel_id)
            df = pd.DataFrame(channel_data)
            st.table(df)

        if st.button("Upload to MongoDB"):
            st.spinner(text="In progress...")
            channel_list = channel_details(channel_id)
            video_ids = get_video_ids(channel_id)
            videos_data = get_video_details(video_ids)
            
            cll1 = db["channel_details"]
            cll1.insert_many(channel_list)

            cll2 = db["video_data"]
            cll2.insert_many(videos_data)

            st.write("Successfully uploaded to MongoDB")
            st.write("Our cloud storage system is MongoDB Atlas")

    # TRANSFORM TAB
    with tab2:    
        st.markdown("# Transformation")
        st.markdown("Select a channel to begin the transformation to SQL")
        ch_names = get_channel_name()
        user_inp = st.selectbox("Select channel", options=ch_names)

    def insert_into_channels():
        coll_channel=db.channel_details
        query = "INSERT INTO channel_data (channel_id, channel_name, channel_description, subscribers, channel_views, channel_total_videos, playlist_id, channel_country) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        for channel in coll_channel.find(user_inp):
            values = (channel["channel_id"],
                      channel["channel_name"], 
                      channel["channel_description"], 
                      channel["subscribers"], 
                      channel["channel_views"], 
                      channel["channel_total_videos"], 
                      channel["playlist_id"], 
                      channel["channel_country"])
            cursor.execute(query, values)
            mydb.commit()
            
    def insert_into_videos():
        coll_video=db.video_data
        for document in coll_video.find(user_inp):
            published_date = datetime.strptime(document['Published_date'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d %H:%M:%S')
            caption_status = 0 if document['Caption_status'] == 'false' else 1
            
    # Map MongoDB document fields to MySQL table columns
            data = {
                'channel_name': document['channel_name'],
                'channel_id': document['channel_id'],
                'video_id': document['video_id'],
                'title': document['title'],
                'thumbnail': document['thumbnail'],
                'Description': document['Description'],
                'Published_date': published_date,
                'Duration': document['Duration'],
                'Views': int(document['Views']),
                'Likes': int(document['Likes']),
                'Comments': int(document['Comments']),
                'Favorite_count': int(document['Favorite_count']),
                'Definition': document['Definition'],
                'Caption_status': caption_status
                }

    # Insert data into MySQL
            cursor.execute("""
                           INSERT INTO video_data
                           (channel_name, channel_id, video_id, title, thumbnail, Description, Published_date, Duration, Views, Likes, Comments, Favorite_count, Definition, Caption_status)
                           VALUES (%(channel_name)s, %(channel_id)s, %(video_id)s, %(title)s, %(thumbnail)s, %(Description)s, %(Published_date)s, %(Duration)s, %(Views)s, %(Likes)s, %(Comments)s, %(Favorite_count)s, %(Definition)s, %(Caption_status)s)
                           """, data)

# Commit changes and close connections
            mydb.commit()

    if st.button("Submit"):
        insert_into_channels()
        insert_into_videos()
        st.success("Transformation to MySQL Successful!")



# VIEW PAGE
if selected == "View":
    
    st.write("## :orange[Select any question to get Insights]")
    questions = st.selectbox('Questions',
    ['1. What are the names of all the videos and their corresponding channels?',
    '2. Which channels have the most number of videos, and how many videos do they have?',
    '3. What are the top 10 most viewed videos and their respective channels?',
    '4. How many comments were made on each video, and what are their corresponding video names?',
    '5. Which videos have the highest number of likes, and what are their corresponding channel names?',
    '6. What is the total number of likes and dislikes for each video, and what are their corresponding video names?',
    '7. What is the total number of views for each channel, and what are their corresponding channel names?',
    '8. What are the names of all the channels that have published videos in the year 2022?',
    '9. What is the duration of all videos in each channel, and what are their corresponding channel names?',
    '10. Which videos have the highest number of comments, and what are their corresponding channel names?'])
    
    if questions == '1. What are the names of all the videos and their corresponding channels?':
        cursor.execute("""SELECT title AS Video_name, channel_name AS Channel_Name
                            FROM video_data
                            ORDER BY channel_name""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        
    elif questions == '2. Which channels have the most number of videos, and how many videos do they have?':
        cursor.execute("""SELECT channel_name AS Channel_Name, channel_total_videos AS Total_Videos
                            FROM channel_data
                            ORDER BY total_videos DESC""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :blue[Number of videos in each channel :]")
        #st.bar_chart(df,x= mycursor.column_names[0],y= mycursor.column_names[1])
        fig = px.bar(df,
                     x=cursor.column_names[0],
                     y=cursor.column_names[1],
                     orientation='v',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)
        
    elif questions == '3. What are the top 10 most viewed videos and their respective channels?':
        cursor.execute("""SELECT channel_name AS Channel_Name, title AS Video_Title, views AS Views 
                            FROM video_data
                            ORDER BY views DESC
                            LIMIT 10""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :green[Top 10 most viewed videos :]")
        fig = px.bar(df,
                     x=cursor.column_names[2],
                     y=cursor.column_names[1],
                     orientation='h',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)
        
    elif questions == '4. How many comments were made on each video, and what are their corresponding video names?':
        cursor.execute("""SELECT channel_name, video_id, title, comments FROM video_data ORDER BY comments DESC LIMIT 10;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
          
    elif questions == '5. Which videos have the highest number of likes, and what are their corresponding channel names?':
        cursor.execute("""SELECT channel_name AS Channel_Name,title AS Title,likes AS likes FROM video_data ORDER BY likes DESC LIMIT 10;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :green[Top 10 most liked videos :]")
        fig = px.bar(df,
                     x=cursor.column_names[2],
                     y=cursor.column_names[1],
                     orientation='h',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)
        
    elif questions == '6. What is the total number of likes and dislikes for each video, and what are their corresponding video names?':
        cursor.execute("""SELECT title AS Title, likes AS likes FROM video_data ORDER BY likes DESC;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
         
    elif questions == '7. What is the total number of views for each channel, and what are their corresponding channel names?':
        cursor.execute("""SELECT channel_name AS Channel_Name, channel_views AS views FROM channel_data ORDER BY channel_views DESC;""")
        
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :green[Channels vs Views :]")
        fig = px.bar(df,
                     x=cursor.column_names[0],
                     y=cursor.column_names[1],
                     orientation='v',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)
        
    elif questions == '8. What are the names of all the channels that have published videos in the year 2022?':
        cursor.execute("""SELECT title AS Channel_Name FROM video_data WHERE published_date LIKE '2022%' GROUP BY title ORDER BY title;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        
    elif questions == '9. What is the duration of all videos in each channel, and what are their corresponding channel names?':
        cursor.execute("""SELECT title AS Channel_Name, duration AS duration FROM video_data ORDER BY title DESC;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :green[video duration for channels :]")
        fig = px.bar(df,
                     x=cursor.column_names[0],
                     y=cursor.column_names[1],
                     orientation='v',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)
        
    elif questions == '10. Which videos have the highest number of comments, and what are their corresponding channel names?':
        cursor.execute("""SELECT title AS Channel_Name,video_id AS Video_ID,comments AS Comments FROM video_data ORDER BY comments DESC LIMIT 10;""")
        df = pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
        st.write(df)
        st.write("### :green[Videos with most comments :]")
        fig = px.bar(df,
                     x=cursor.column_names[1],
                     y=cursor.column_names[2],
                     orientation='v',
                     color=cursor.column_names[0]
                    )
        st.plotly_chart(fig,use_container_width=True)


# Set the home page and options
if selected == "Home":
    cl1, cl2 = st.columns(2, gap="large")
    cl1.image("https://cdn.freebiesupply.com/logos/large/2x/youtube-2-logo-png-transparent.png")
    cl1.markdown("## :blue[Domain] : Social Media ('Youtube')")
    cl1.markdown("## :blue[Technologies used] : Python scripting, Youtube Data retrieval using API, Streamlit")
    cl1.markdown("## :blue[Overview] : Retrieving the YouTube channel data from the Google API, storing it in MongoDB as a data lake, migrating and transforming data into a SQL database, then querying the data and displaying it in the Streamlit app.")
    
    cl2.markdown("## :blue[Name] : Preetha")
    cl2.markdown("## :blue[email] : preethajayaseelan@gmail.com")
    cl2.markdown("## :blue[Batch id] : DTM9")