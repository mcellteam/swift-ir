#include <stdio.h>
#include <math.h>
#define	NG 300
#define NS 9
#define R (NG/NS)
float g[NG];
float s[NS];
float xs[NG];
float p[NG];
float e[NG];
float er[NG];
main() {
	float a, x, v, d, err, sume2 = 0;
	int i, j, k;
	for(i = 0; i < NG; i++) {
		a = i*2*M_PI/NG;
		//v = .25*sin(a+.1)+.5*cos(3*a+.3)+.3*cos(6*a);
		v = sin(a+.9);
		e[i] = v;
	}
	for(i = 0; i < NS; i++)
		s[i] = e[i*R];
	for(i = NG/2+1; i < NG; i++) {
		x = (1.5*3.14159/R)*(i-NG/2);
		v = sin(x)/x;
		xs[i] = x;
		p[i] = v;
		p[NG-i] = v;
	}
	p[NG/2] = 1.;
	for(i = 0; i < NS; i++)
		for(j = 0; j < NG; j++) {
			k = R*i + (j-NG/2);
fprintf(stderr, "%d %d %d  %d\n", i, j, k, R);
			if(k >= 0 && k < NG)
				g[k] += s[i]*p[j];
		}
	for(i = 0; i < NS; i++)
		printf("%d %f\n", R*i, s[i]);
	printf("\n");
	//for(i = 0; i < NG; i++)
		//printf("%d %f\n", i, xs[i]);
	//printf("\n");
	for(i = 0; i < NG; i++)
		printf("%d %f\n", i, e[i]);
	printf("\n");
	for(i = 0; i < NG; i++)
		printf("%d %f\n", i, p[i]);
	printf("\n");
	for(i = 0; i < NG; i++)
		printf("%d %f\n", i, g[i]);
	for(i = 0; i < NG; i++)  {
		err = e[i] - g[i];
		er[i] = err;
		sume2 = err*err;
	}
/*
	printf("\n");
	for(i = 0; i < NG; i++)
		printf("%d %f\n", i, er[i]);
*/
	fprintf(stderr, "rms %f  %f\n", sqrt(sume2), sume2);
}
