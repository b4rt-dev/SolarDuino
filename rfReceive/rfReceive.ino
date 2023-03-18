/*
 * Very basic code to recieve messages and print them over serial for easy logging on pc
 */

#include <RH_ASK.h>
#include <SPI.h> 
 
RH_ASK rf_driver;

struct sensorStruct{
  float vSol;
  float aSol;
  float vBat;
  float aOut;
  float vcc;
  uint8_t flags;
}SensorReadings;
 
void setup()
{
  rf_driver.init();
  Serial.begin(115200);

  SensorReadings.vBat = 0.0;
  SensorReadings.vSol = 0.0;
  SensorReadings.aSol = 0.0;
  SensorReadings.aOut = 0.0;
  SensorReadings.vcc = 0.0;
  SensorReadings.flags = 0;
}

void receiveValues()
{
  uint8_t buf[sizeof(SensorReadings)];
  uint8_t len = sizeof(buf);
  if (rf_driver.recv(buf, &len))
  {
    memcpy(&SensorReadings, buf, sizeof(SensorReadings));
    Serial.print(SensorReadings.vSol, 5);
    Serial.print(", ");
    Serial.print(SensorReadings.aSol, 5);
    Serial.print(", ");
    Serial.print(SensorReadings.vBat, 5);
    Serial.print(", ");
    Serial.print(SensorReadings.aOut, 5);
    Serial.print(", ");
    Serial.print(SensorReadings.vcc, 5);
    Serial.print(", ");
    Serial.println(SensorReadings.flags);
  }
}
 
void loop()
{
    receiveValues();
}
