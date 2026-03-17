#include <Wire.h>
#include "Adafruit_SHT31.h"
#include "RTClib.h"

Adafruit_SHT31 sht31 = Adafruit_SHT31();
RTC_DS3231 rtc;

const int mq2Pin = A0;

void setup() {
  Serial.begin(9600);
  sht31.begin(0x44);
  rtc.begin();

  // Header CSV
  Serial.println("Date,Time,Temperature,Humidity,Gas");
}

void loop() {
  DateTime now = rtc.now();

  float temp = sht31.readTemperature();
  float hum  = sht31.readHumidity();
  int gas    = analogRead(mq2Pin);

  Serial.print(now.year()); Serial.print("-");
  Serial.print(now.month()); Serial.print("-");
  Serial.print(now.day()); Serial.print(",");

  Serial.print(now.hour()); Serial.print(":");
  Serial.print(now.minute()); Serial.print(":");
  Serial.print(now.second()); Serial.print(",");

  Serial.print(temp); Serial.print(",");
  Serial.print(hum);  Serial.print(",");
  Serial.println(gas);

  delay(5000);
}
