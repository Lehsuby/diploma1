# -*- coding: utf-8 -*-
#! /usr/bin/env python
from subprocess import call
import cv2
import time as ttime
from skimage.measure  import compare_ssim as ssim
from os import path,makedirs,remove
import shutil
import moviepy.editor
from moviepy.video.tools.subtitles import SubtitlesClip, file_to_subtitles
import pysrt
import smtplib
import argparse

ERROR_MSG = "В вашем файле (%s) обнаружена ошибка, попробуйте другой видеофайл\n http://localhost:8081/"
MAIN_DIRECTORY = "/home/lehsuby/PycharmProjects/diploma1/upload_files/"
RESULT_DIRECTORY = "/home/lehsuby/PycharmProjects/diploma1/result_files/"

def check_video(video_path,email,first_file_name):
    vidcap = cv2.VideoCapture(video_path)
    success, image = vidcap.read()
    if not success:
        send_email(email,ERROR_MSG % first_file_name, first_file_name)
        remove(video_path)
    return success

def spliting_on_frames (video_path, user_id,ssim_id):
    directory = MAIN_DIRECTORY+"%d" % user_id
    if not path.exists(directory):
        makedirs(directory)

    vidcap = cv2.VideoCapture(video_path)
    success, image1 = vidcap.read()
    count_time = 0
    count_frames = 0
    frames_at_sec = 1000
    info_frame = []
    if success:
        cv2.imwrite(MAIN_DIRECTORY+'%d/%d.png' % (user_id, count_frames), image1)
        info_frame.append((count_frames,count_time))
        count_time += 1
        count_frames += 1
        vidcap.set(cv2.CAP_PROP_POS_MSEC, (count_time * frames_at_sec))
        success, image2 = vidcap.read()
        while success:
            s, diff = ssim(image1, image2, full=True, multichannel=True)
            if s<ssim_id:
                cv2.imwrite(MAIN_DIRECTORY+'%d/%d.png' % (user_id, count_frames), image2)
                info_frame.append((count_frames, count_time))
                image1 = image2
                count_frames +=1
            count_time += 1
            vidcap.set(cv2.CAP_PROP_POS_MSEC, (count_time * frames_at_sec))
            success, image2 = vidcap.read()
    return info_frame

def image_captioning(user_id, model_path,count_frames):
    f = open(MAIN_DIRECTORY+'%d/logfile_1.txt' % user_id,'w')
    image_path = MAIN_DIRECTORY+'%d/' % user_id
    call_string = "docker run -it -d -v %s:/data/model -v %s:/data/images samnco/neuraltalk2:latest" % (model_path,image_path)
    call(call_string, stdout=f, shell=True)
    with open(MAIN_DIRECTORY+'%d/logfile_1.txt' % user_id,'r') as f:
        result = f.read()
    while True:
        f = open(MAIN_DIRECTORY+'%d/logfile_2.txt' % user_id, 'w')
        call("docker logs "+ result, stdout=f, shell=True)
        with open(MAIN_DIRECTORY+'%d/logfile_2.txt' % user_id,'r') as f:
            line = f.read().replace('\n', '')
        if line.find("loss:") != -1:
            break
        ttime.sleep(2)

    with open(MAIN_DIRECTORY+'%d/logfile_2.txt' % user_id,'r') as f:
        data = f.readlines()
    dataset = []
    for i in range(count_frames):
        frame_id = int(change_line(data[3 * i + 5], "images/", 7, "."))
        annotation = change_line(data[3 * i + 6], ":", 2, "\x1b[0m")
        dataset.append((frame_id, annotation))
    dataset = sorted(dataset, key=lambda x: x[0])
    return dataset

def change_line(line, start_str, step_start, end_str):
    index_start = line.find(start_str) + step_start
    index_end = line.find(end_str, index_start)
    line = line[index_start:index_end]
    return line

def make_subtitles(frames_time, frames_annotation,user_id):
    file = pysrt.SubRipFile(encoding='utf-8')
    length = len(frames_time)
    for i in range(length-1):
        sub = pysrt.SubRipItem()
        sub.index = frames_time[i][0]+1
        sub.start.seconds = frames_time[i][1]
        sub.end.seconds = frames_time[i+1][1]
        sub.text = frames_annotation[i][1]
        file.append(sub)
    sub = pysrt.SubRipItem()
    sub.index = frames_time[length-1][0]+1
    sub.start.seconds = frames_time[length-1][1]
    sub.text = frames_annotation[length-1][1]
    file.append(sub)
    file.save(MAIN_DIRECTORY+'%d/subtitles.srt' % user_id)

def make_video_with_subtitles(video_path, user_id):
    generator = lambda txt: moviepy.editor.TextClip(txt, font='Arial', fontsize=30, color='white')
    sub = file_to_subtitles(MAIN_DIRECTORY+'%d/subtitles.srt' % user_id)
    subtitles = SubtitlesClip(sub, generator)

    video = moviepy.editor.VideoFileClip(video_path)
    result = moviepy.editor.CompositeVideoClip([video, subtitles.set_position(('center', 'bottom'))])

    result.to_videofile(RESULT_DIRECTORY+'video_%d.mp4' % (user_id),
                        fps=video.fps, audio_codec = 'libmp3lame', verbose=False, logger=None,
                        temp_audiofile = RESULT_DIRECTORY+'temp-audio_%d.mp3' % (user_id), remove_temp = True)

def send_email(addr_to, msg_text, first_file_name):
    host = "smtp.gmail.com"
    subject = first_file_name
    addr_from = "video.recognition.info@gmail.com"
    password = ""

    BODY = "\r\n".join((
        "From: %s" % addr_from,
        "To: %s" % addr_to,
        "Subject: %s" % subject,
        "",
        msg_text + "\n Данная ссылка активна в течение 24 часов."
    ))

    server = smtplib.SMTP(host, 587)
    server.starttls()
    server.login(addr_from,password)
    server.sendmail(addr_from, [addr_to], BODY)
    server.quit()

def main(params):
    user_id = params['user_id']
    email = params['email']
    first_file_name = params['first_file_name']
    model_path = "/home/lehsuby/PycharmProjects/neuraltalk2/models"
    video_path = "/home/lehsuby/IdeaProjects/WEBProjectDiploma/target/WEBProject-1.0-SNAPSHOT/upload_files/%d/%s" % (user_id, first_file_name)
    ssim_id = params['ssim']

    print user_id
    print "check_video"
    check = check_video(video_path,email,first_file_name)
    if check:
        print "spliting_on_frames"
        frames_time = spliting_on_frames(video_path, user_id,ssim_id)
        print "image_captioning"
        frames_annotation = image_captioning(user_id, model_path, len(frames_time))
        print "make_subtitles"
        make_subtitles(frames_time, frames_annotation, user_id)
        print "make_video"
        make_video_with_subtitles(video_path, user_id)
        print "send_mail"
        msg_text = "http://localhost:8081/results?user_id=%d" % user_id
        send_email(email, msg_text,first_file_name)

        shutil.rmtree(MAIN_DIRECTORY + '%d' % user_id)



if __name__ == "__main__":

  parser = argparse.ArgumentParser()
  parser.add_argument('--user_id', type=long)
  parser.add_argument('--email', type=str)
  parser.add_argument('--first_file_name', type=str)
  parser.add_argument('--ssim', default=0.7, type=float)

  args = parser.parse_args()
  params = vars(args)
  main(params)

