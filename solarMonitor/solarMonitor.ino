/*
 * Quick and dirty code, will make nice when PCB is done
 * NOTE: for pin 10 to work you need to remove the ptt pin code in RH_ASK.cpp
 */

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_PCD8544.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <RH_ASK.h> // NOTE: for pin 10 to work you need to remove the ptt pin code in RH_ASK.cpp

// PINS
#define N_POWER_DOWN_OPAMP  2
#define DISPLAY_SCLK        3
#define DISPLAY_DIN         4
#define DISPLAY_DC          5
#define DISPLAY_CS          6
#define DISPLAY_RST         7
#define ANALOG_BAT_V        A0
#define ANALOG_SOLAR_A      A2
#define ANALOG_SOLAR_V      A3
#define MOSFET_VBAT         10

#define FLOAT_DECIMALS      3

#define INA219_A_CORRECTION 0.15

// Discharge threshold in V
#define DISCHARGE_TRESHOLD_TOP    3.9
#define DISCHARGE_TRESHOLD_BOTTOM 3.5

Adafruit_INA219 ina219;

Adafruit_PCD8544 display = Adafruit_PCD8544(
  DISPLAY_SCLK,
  DISPLAY_DIN,
  DISPLAY_DC,
  DISPLAY_CS,
  DISPLAY_RST
);

RH_ASK rf_driver;

struct sensorStruct{
  float vSol;
  float aSol;
  float vBat;
  float aOut;
  float vcc;
  uint8_t flags;
}SensorReadings;

byte buf[sizeof(SensorReadings)] = {0};

bool allow_discharge = false;

void setupDisplay()
{
  display.begin();
  display.setContrast(60);
  display.clearDisplay();

  display.setRotation(2);
  display.setTextSize(1);
  display.setTextColor(BLACK);
  display.setCursor(0,0);
  display.println("SolarMon");
  
  display.display();
}

void setupPins()
{
  pinMode(MOSFET_VBAT, OUTPUT);
  digitalWrite(MOSFET_VBAT, LOW); // Start off
}

void setup()
{
  setupPins();
  setupDisplay();
  ina219.begin();

  rf_driver.init();

  SensorReadings.vBat = 0.0;
  SensorReadings.vSol = 0.0;
  SensorReadings.aSol = 0.0;
  SensorReadings.aOut = 0.0;
  SensorReadings.vcc = 0.0;
  SensorReadings.flags = 0;
}

void sendValues()
{
  byte len = sizeof(SensorReadings);
  memcpy(buf, &SensorReadings, len);
  rf_driver.send(buf, len);
  rf_driver.waitPacketSent();
}

float readVoltage(uint8_t pin)
{
  // Resistor divider using:
  // r1 = 300k
  // r2 = 100k
  // Real voltage = measured voltage * 4
  int analogValue = analogRead(pin);
  float analogVoltage = analogValue * ( readVcc() / 1023.0);
  return analogVoltage * 4;
}

float readVcc()
{
  // Read 1.1V reference against AVcc
  // set the reference to Vcc and the measurement to the internal 1.1V reference
  ADMUX = (1<<REFS0) | (1<<MUX3) | (1<<MUX2) | (1<<MUX1);
  delay(2); // Wait for Vref to settle
  ADCSRA |= (1<<ADSC); // Start conversion
  while (bit_is_set(ADCSRA,ADSC)); // measuring
  unsigned int result = ADC;
  //custom scale factor, processor specific
  result = 1125300UL / (unsigned long)result; // Calculate Vcc (in mV); 1125300 = 1.1*1024*1000
  return float(result)/1000; // Vcc in Volts as float
}

void updateDisplay(float Vcc, float solarCurrent, float solarVoltage, float batteryVoltage)
{
  display.clearDisplay();
  display.setCursor(0, 0);
  
  display.print("Solar  ");
  display.print(solarVoltage, FLOAT_DECIMALS);
  display.println("V");
  
  display.print("       ");
  display.print(solarCurrent, 0);
  display.setCursor(72, 8);
  display.println("mA");

  display.println("");
  display.print("Bat    ");
  display.print(batteryVoltage, FLOAT_DECIMALS);
  display.println("V");

  display.println("");
  display.print("Vcc    ");
  display.print(Vcc, FLOAT_DECIMALS);
  display.println("V");
  
  display.display();
}

void loop()
{

  float vBatMean = 0.0;
  float vSolMean = 0.0;
  float aSolMean = 0.0;
  float aOutMean = 0.0;
  float vccMean = 0.0;

  int loops = 5;
  
  for(int i = 0; i < loops; i++)
  {
    float Vcc = readVcc();
    float solarCurrent = ina219.getCurrent_mA() + INA219_A_CORRECTION;
    float solarVoltage = ina219.getBusVoltage_V();
    float batteryVoltage = readVoltage(ANALOG_BAT_V);
  
    vBatMean += batteryVoltage;
    vSolMean += solarVoltage;
    aSolMean += solarCurrent;
    aOutMean += 0.0;
    vccMean += Vcc;
    
    updateDisplay(Vcc, solarCurrent, solarVoltage, batteryVoltage);
    delay(100);
  }

  // Enable discharge mode when above certain treshold
  if (vBatMean/loops > DISCHARGE_TRESHOLD_TOP)
  {
    allow_discharge = true;
  }
  // Enable mosfet
  if (allow_discharge && vBatMean/loops > DISCHARGE_TRESHOLD_BOTTOM)
  {
    digitalWrite(MOSFET_VBAT, HIGH);
  }
  else // When almost empty, disable discharge mode
  {
    allow_discharge = false;
    digitalWrite(MOSFET_VBAT, LOW);
  }

  SensorReadings.vBat = vBatMean/loops;
  SensorReadings.vSol = vSolMean/loops;
  SensorReadings.aSol = aSolMean/loops;
  SensorReadings.aOut = aOutMean/loops;
  SensorReadings.vcc = vccMean/loops;
  SensorReadings.flags = 0;

  sendValues();
}
