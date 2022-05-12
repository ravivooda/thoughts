## TLDR

Created an automated alert via IFTTT when MyQ failed me, that alerts me if the garage door is left open for a really long time

## Problem

We have a garage door. It's a smart garage door with Chamberlain's MyQ Garage Door Opener. It's WiFi enabled, it has an app, there is a garage switch plugged into the wall, and a couple of Remote Garage Door openers that we use from time to time in the car. 

With all of this functionality, it becomes easy to open, close the door. Again, with ALL of this FUNCTIONALITY, you can OPEN and CLOSE the DOOR! 

When we wish to take the car out of the garage, we need to 

1. Sit in the car
2. Buckle Up!
3. Click the Remote Garage Door Key to open the garage door
4. Drive the car outside of the garage
5. Stop
6. Click the Remote Garage Door Key to close the garage door
7. Crouch and observe the Garage Door Closing in the wing mirror of the car
8. Drive off!

I tried creating a mind map of all the above steps, but from time to time, I tend to forget the 6, 7 steps, aka leave the Garage Door Open. Our neighbours, our very generous neighbours, have been patiently sending us messages, calling us whenever that happens. I believe there was only one time when we came back, and the garage door was still open, and me or my wife did not receive a call. So our neighbours have looked after us more than any Smart thing at our home so far.

Anyway, my tech brain kept saying MyQ should have provided this functionality, i.e. Alert when the garage door has been left open for X minutes. I navigated the app, and found that I could setup an alert in the app! It was going to be easy peasy! So

1. Opened the MyQ App
2. Clicked on the three dots beside the Door Name
3. Clicked on Notifications and Alerts
4. Cliced on "Add Access Notification"
5. Gave a notification name
6. Selected opened, and unselected every other option there is
7. And stuck! 

MyQ, although should the option to "Remind Me", has disabled the option! I'm not kidding, see the picture below 

![IMG_E731FEC2C933-1](https://user-images.githubusercontent.com/3404838/168114607-0386c3f4-5a4e-44a7-aaca-b3241dc0319c.jpeg)

I investigated more about this, but really couldn't work around this. My only explanation is MyQ won't support the functionality unless I get an additional [device](https://www.amazon.com/gp/product/B00B7CDSQ8/ref=ask_ql_qh_dp_hza) (just for alerts). It seems it used to be [supported](https://community.smartthings.com/t/myq-garage-rule/19498/4), and they disabled it! Or maybe I'm just a dumb person whose fingers have gotten fatter.

## Solution

Although my neighbours have been excellent for our Garage Door Left Open alert, I don't want to keep leaching off their generosity. So I dedided to find alternate solutions. Here are some I thought of:

1. ~~Train a bird~~ Get a pet bird, feed it, train it to call us through our homepod in the home if the garage door was not shut for a long time. Strenuous but doable, but the real problem lies in me taking awfully long time in selecting a bird.
2. Get a [Door sensor](https://www.ecobee.com/en-us/accessories/smart-door-window-sensor/) like the ones we have at home for our doors. Very efficient, pricey, works really well with homekit. 
3. IFTTT to rescue.

### IFTTT

MyQ integrates with IFTTT (but not Homekit!!!) so I created an account in IFTTT, gave acess to my MyQ Garage Door Opener. (If you are thinking ohh juicy details, let me mess with his garage door now that its connected to IFTTT, I would love for you to try. I will also learn from you, so go ahead. Today it only has access to listen to Triggers)

#### Door Opened Trigger

Then I created an Applet in IFTTT to listen to the MyQ door opened. When the trigger goes off, it calls the [delay webhook](https://help.ifttt.com/hc/en-us/articles/360059005834-How-to-add-a-delay-to-an-IFTTT-action)

![IMG_26BB404D97BD-1](https://user-images.githubusercontent.com/3404838/168118613-9318971e-cc91-4893-ab9f-397194230cab.jpeg)

This delay is essentially a time to start the next applet

#### Door Left Opened Alert Trigger

When the delay expires, the IFTTT webhook will emit a "Event Name" into their Maker service, which I used the trigger for alerting. So a second Applet was created which has the trigger of Receiving a web request for a specific "Event Name", which then pushes me a notification when the alert is triggered.

![IMG_83A75CF362D7-1](https://user-images.githubusercontent.com/3404838/168119354-e90fdd45-a19b-4d24-b653-82947c2e5769.jpeg)

#### Cancel Alert Trigger 

Alerting everytime the door is opened is not very helpful. Especially when I remembered to close the door, and indeed closed the door. So I setup another applet which cancels the delay webhook request, and clears out all notifications in the maker channel.

![IMG_02876031C5CF-1](https://user-images.githubusercontent.com/3404838/168119958-6d5dcbe2-29f3-4ba0-a796-269453479907.jpeg)

#### Announce Notifcations

Since I use Carplay I wanted Siri to alert me immediately when receiving alerts from IFTTT, and announce whenever possible.

#### Ending

Overall this was fun experience. It felt like I was revisiting Automata lectures from school. I ran the applets a few times, tested that the alerts are working, opened and closed my garage a few times (which could look maniac for outsiders). And I will continue to monitor a few more times.
