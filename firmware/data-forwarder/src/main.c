/*
 * Edge Impulse "data forwarder" firmware
 * Board : Arduino UNO Q  (STM32U585 side, Zephyr)
 * Shield: X-NUCLEO-IKS4A1 (LIS2DUXS12 3-axis accelerometer)
 *
 * What it does: reads the accelerometer 100 times per second and prints
 * one line per reading on the serial console, formatted exactly the way the
 * Edge Impulse data forwarder expects:
 *
 *     -0.120,-6.200,7.900
 *
 * On your laptop you then run `edge-impulse-data-forwarder`, which reads these
 * lines and uploads them to your Edge Impulse project as labelled samples.
 *
 * Build:  west build --pristine -b arduino_uno_q -- -DSHIELD=x_nucleo_iks4a1
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <stdio.h>

/* 100 Hz sampling = one reading every 10 ms.
 * IMPORTANT: use the same 100 Hz when you design your impulse in Edge Impulse Studio. */
#define SAMPLE_PERIOD_MS 10

int main(void)
{
	/* Make printf() send each line immediately instead of buffering it. */
	setvbuf(stdout, NULL, _IONBF, 0);

	/* Find the LIS2DUXS12 that the x_nucleo_iks4a1 shield overlay put on the I2C bus. */
	const struct device *accel = DEVICE_DT_GET_ONE(st_lis2duxs12);

	if (!device_is_ready(accel))
	{
		/* This is the only non-data line we ever print, and only on failure. */
		printf("ERROR: LIS2DUXS12 not ready. Check the shield is seated and J4/J5 are in Mode 1.\n");
		return 0;
	}

	/* Configure the sensor: 200 Hz internal rate (>= 2x our 100 Hz read rate), +/-2 g range. */
	struct sensor_value odr = {.val1 = 200, .val2 = 0};
	struct sensor_value fs;

	sensor_attr_set(accel, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
	sensor_g_to_ms2(2, &fs);
	sensor_attr_set(accel, SENSOR_CHAN_ACCEL_XYZ, SENSOR_ATTR_FULL_SCALE, &fs);

	/* Give the sensor a moment to start producing data. */
	k_sleep(K_MSEC(100));

	/* Use an absolute schedule so the rate stays at exactly 100 Hz
	 * regardless of how long the I2C read takes. */
	int64_t next_tick = k_uptime_get();

	while (1)
	{
		next_tick += SAMPLE_PERIOD_MS;

		struct sensor_value xyz[3];

		if (sensor_sample_fetch(accel) == 0)
		{
			sensor_channel_get(accel, SENSOR_CHAN_ACCEL_XYZ, xyz);

			/* Units are m/s^2 - the same units the inference firmware uses later,
			 * so training data and live data match. */
			printf("%.3f,%.3f,%.3f\n",
				   sensor_value_to_double(&xyz[0]),
				   sensor_value_to_double(&xyz[1]),
				   sensor_value_to_double(&xyz[2]));
		}

		k_sleep(K_TIMEOUT_ABS_MS(next_tick));
	}

	return 0;
}
