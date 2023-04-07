/*
 * WARNING: for pin 10 to not short to gnd when pressing the left button, you need to remove the ptt pin code in RH_ASK.cpp!
 *            (since it overrides pinmode to output and button is directly wired to gnd when pressed)
 * NOTE: display glitches at the lower lines when charging hard and battery is ~4v.
 *        Need to diagnose. For now I changed software SPI from 4MHz to 1MHz in adafruit library
 *  
 *  
 */

//*****************
// INCLUDES
//*****************

#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_PCD8544.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include <RH_ASK.h> // NOTE: for pin 10 to work you need to remove the ptt pin code in RH_ASK.cpp

//*****************
// DEFINES
//*****************

// PINS
#define DISPLAY_SCLK        3
#define DISPLAY_DIN         4
#define DISPLAY_DC          5
#define DISPLAY_CS          6
#define DISPLAY_RST         7

#define BTN_UP              8
#define BTN_DOWN            9
#define BTN_LEFT            10
#define BTN_RIGHT           11

#define RF_TX               12

#define SW_3V3              2
#define SW_VBAT             13
#define SW_5V               A3

#define EN_3V3              A0
#define EN_VBAT             A1
#define EN_5V               A2

#define PIN_SDA             A4
#define PIN_SCL             A5


// DISPLAY CONFIG
#define FLOAT_DECIMALS      3

// INA219
#define INA_SOLAR_ADDRESS         0x40
#define INA_OUTPUT_ADDRESS        0x45
#define INA_SOLAR_A_CORRECTION    0.15
#define INA_OUTPUT_A_CORRECTION   0.0
#define INA_SOLAR_V_CORRECTION    0.011
#define INA_OUTPUT_V_CORRECTION   0.018

// HOW MANY ITERATIONS AND DELAY TO AVERAGE SENSOR READINGS
#define SENSOR_READ_LOOPS         5
#define SENSOR_LOOPS_DELAY_MS     100

//*****************
// GLOBAL VARIABLES
//*****************

Adafruit_INA219 ina_solar(INA_SOLAR_ADDRESS);  // Connected to solar panel
Adafruit_INA219 ina_output(INA_OUTPUT_ADDRESS); // Connected to output of battery

// Nokia status display
Adafruit_PCD8544 display = Adafruit_PCD8544(
  DISPLAY_SCLK,
  DISPLAY_DIN,
  DISPLAY_DC,
  DISPLAY_CS,
  DISPLAY_RST
);

// 433MHz Transmitter
RH_ASK rf_driver;


// Data structure for sensor readings to transmit
struct sensorStruct{
  float vSol;
  float aSol;
  float vBat;
  float aOut;
  float vcc;
  uint8_t flags;
} SensorReadings;

// Transmit buffer of sensor readings
byte sensorTXbuf[sizeof(SensorReadings)] = {0};

bool allow_discharge = false; // TODO replace with new code

bool treshold_3v3_reached = false;
bool treshold_vbat_reached = false;
bool treshold_5v_reached = false;

// Discharge thresholds in V with default values
float treshold_3v3_on = 3.6;
float treshold_3v3_off = 3.4;

float treshold_vbat_on = 3.8;
float treshold_vbat_off = 3.6;

float treshold_5v_on = 4.0;
float treshold_5v_off = 3.65;


//*****************
// FUNCTIONS
//*****************

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
  // Output enables, start off
  pinMode(EN_3V3, OUTPUT);
  digitalWrite(EN_3V3, LOW);

  pinMode(EN_VBAT, OUTPUT);
  digitalWrite(EN_VBAT, LOW);

  pinMode(EN_5V, OUTPUT);
  digitalWrite(EN_5V, LOW);

  // Switches
  pinMode(SW_3V3, INPUT);
  pinMode(SW_VBAT, INPUT);
  pinMode(SW_5V, INPUT);

  // Buttons
  pinMode(BTN_UP, INPUT);
  pinMode(BTN_DOWN, INPUT);
  pinMode(BTN_LEFT, INPUT);
  pinMode(BTN_RIGHT, INPUT);
}

void setup()
{
  setupPins();
  setupDisplay();
  ina_solar.begin();
  ina_output.begin();
  rf_driver.init();

  // Initialize sensor reading values
  SensorReadings.vBat = 0.0;
  SensorReadings.vSol = 0.0;
  SensorReadings.aSol = 0.0;
  SensorReadings.aOut = 0.0;
  SensorReadings.vcc = 0.0;
  SensorReadings.flags = 0;
}

void sendValues()
{
  // Transmit sensor readings over 433MHz
  byte len = sizeof(SensorReadings);
  memcpy(sensorTXbuf, &SensorReadings, len);
  rf_driver.send(sensorTXbuf, len);
  rf_driver.waitPacketSent();
}

float readVcc()
{
  // (copied this code from the Arduino forum)
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

void updateDisplay()
{
  display.clearDisplay();
  display.setCursor(0, 0);
  
  display.print("Solar  ");
  display.print(SensorReadings.vSol, FLOAT_DECIMALS);
  display.println("V");
  
  display.print("       ");
  display.print(SensorReadings.aSol, 0);
  display.setCursor(72, 8);
  display.println("mA");

  display.print("Output ");
  display.print(SensorReadings.vBat, FLOAT_DECIMALS);
  display.println("V");
  
  display.print("       ");
  display.print(SensorReadings.aOut, 0);
  display.setCursor(72, 24);
  display.println("mA");

  display.println("");
  display.print("Vcc    ");
  display.print(SensorReadings.vcc, FLOAT_DECIMALS);
  display.println("V");
  
  display.display();
}


void manageDischargeOutputs()
{
  // TODO: SensorReadings.flags;

  //*****
  // 3V3
  //*****
  // Manual override
  if (digitalRead(SW_3V3))
  {
    digitalWrite(EN_3V3, HIGH);
  }
  else
  {
    // Enable discharge mode when above upper treshold
    if (SensorReadings.vBat > treshold_3v3_on)
    {
      treshold_3v3_reached = true;
    }
    // Enable output as long as above lower treshold
    if (treshold_3v3_reached && SensorReadings.vBat > treshold_3v3_off)
    {
      digitalWrite(EN_3V3, HIGH);
    }
    // Otherwise, disable output
    else
    {
      treshold_3v3_reached = false;
      digitalWrite(EN_3V3, LOW);
    }
  }


  //******
  // VBAT
  //******
  // Manual override
  if (digitalRead(SW_VBAT))
  {
    digitalWrite(EN_VBAT, HIGH);
  }
  else
  {
    // Enable discharge mode when above upper treshold
    if (SensorReadings.vBat > treshold_vbat_on)
    {
      treshold_vbat_reached = true;
    }
    // Enable output as long as above lower treshold
    if (treshold_vbat_reached && SensorReadings.vBat > treshold_vbat_off)
    {
      digitalWrite(EN_VBAT, HIGH);
    }
    // Otherwise, disable output
    else
    {
      treshold_vbat_reached = false;
      digitalWrite(EN_VBAT, LOW);
    }
  }


  //****
  // 5V
  //****
  // Manual override
  if (digitalRead(SW_5V))
  {
    digitalWrite(EN_5V, HIGH);
  }
  else
  {
    // Enable discharge mode when above upper treshold
    if (SensorReadings.vBat > treshold_5v_on)
    {
      treshold_5v_reached = true;
    }
    // Enable output as long as above lower treshold
    if (treshold_5v_reached && SensorReadings.vBat > treshold_5v_off)
    {
      digitalWrite(EN_5V, HIGH);
    }
    // Otherwise, disable output
    else
    {
      treshold_5v_reached = false;
      digitalWrite(EN_5V, LOW);
    }
  }
}


void readSensors()
{
  float vBatMean = 0.0;
  float vSolMean = 0.0;
  float aSolMean = 0.0;
  float aOutMean = 0.0;
  float vccMean = 0.0;

  for(int i = 0; i < SENSOR_READ_LOOPS; i++)
  {
    float Vcc = readVcc();
    // For voltage, we add the shunt voltage to get the voltage of the solar panel or battery, not the circuit
    float solarVoltage = ina_solar.getBusVoltage_V() + (ina_solar.getShuntVoltage_mV() / 1000) - INA_SOLAR_V_CORRECTION;
    float solarCurrent = ina_solar.getCurrent_mA() + INA_SOLAR_A_CORRECTION;
    float batteryVoltage = ina_output.getBusVoltage_V() + (ina_output.getShuntVoltage_mV() / 1000) - INA_OUTPUT_V_CORRECTION;
    float outputCurrent = ina_output.getCurrent_mA() + INA_OUTPUT_A_CORRECTION;
  
    vSolMean += solarVoltage;
    aSolMean += solarCurrent;
    vBatMean += batteryVoltage;
    aOutMean += outputCurrent;
    vccMean += Vcc;
    
    delay(SENSOR_LOOPS_DELAY_MS);
  }

  SensorReadings.vBat = vBatMean/SENSOR_READ_LOOPS;
  SensorReadings.vSol = vSolMean/SENSOR_READ_LOOPS;
  SensorReadings.aSol = aSolMean/SENSOR_READ_LOOPS;
  SensorReadings.aOut = aOutMean/SENSOR_READ_LOOPS;
  SensorReadings.vcc = vccMean/SENSOR_READ_LOOPS;
}

void loop()
{
  readSensors();
  updateDisplay();
  manageDischargeOutputs();
  sendValues();
}
